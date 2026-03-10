"""Session-context runtime helpers for codex-session refresh."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from spawn.contracts.envelopes import utc_now


SUPPORTED_TRIGGERS = {"manual", "path", "timer"}
TRIGGER_PREFIX = "trigger:"
ZERO_HASH = "0" * 64
SUMMARY_SECTION_KEYS = [
    "active_objectives",
    "proposal_refs",
    "backlog_item_refs",
    "open_gate_refs",
    "next_steps",
]

PROPOSAL_REF_RE = re.compile(r"proposal_register/[A-Za-z0-9._/\-]+(?:\.json)?")
BACKLOG_REF_RE = re.compile(r"\bT\d+\b")
GATE_REF_RE = re.compile(r"\b(?:SCX|SCR|ACM)-\d+\b")

SCHEMA_FILES = {
    "session_context": "contracts/session_context/session_context.v1.schema.json",
    "session_context_diff": "contracts/session_context/session_context.diff.v1.schema.json",
    "session_context_sync_event": "contracts/session_context/session_context.sync_event.v1.schema.json",
    "fresh_session_loader_report": "contracts/session_context/fresh_session_loader_report.v1.schema.json",
}


@dataclass(frozen=True)
class SessionContextPaths:
    root: Path
    current_context: Path
    latest_pointer: Path
    diff_dir: Path
    sync_event_dir: Path
    loader_report_dir: Path

    def current_context_ref(self) -> str:
        return "CODEX_STATE/session_context/current/session_context.v1.json"

    def latest_pointer_ref(self) -> str:
        return "CODEX_STATE/session_context/latest.json"

    def diff_ref(self, path: Path) -> str:
        return f"CODEX_STATE/session_context/diffs/{path.name}"

    def sync_event_ref(self, path: Path) -> str:
        return f"CODEX_STATE/session_context/sync_events/{path.name}"


@dataclass(frozen=True)
class SessionContextSyncResult:
    trigger: str
    current_ref: str
    latest_ref: str
    sync_event_ref: str
    diff_ref: str | None
    status: str
    action: str
    context_hash: str

    def summary_line(self) -> str:
        parts = [
            f"session_context={self.current_ref}",
            f"latest={self.latest_ref}",
            f"sync_event={self.sync_event_ref}",
            f"status={self.status}",
            f"action={self.action}",
            f"trigger={self.trigger}",
        ]
        if self.diff_ref:
            parts.append(f"diff={self.diff_ref}")
        return " ".join(parts)


@dataclass(frozen=True)
class FreshSessionLoadResult:
    report_ref: str
    target_session_id: str
    status: str
    source_context_ref: str
    output_context_hash: str | None

    def summary_line(self) -> str:
        parts = [
            f"loader_report={self.report_ref}",
            f"target_session_id={self.target_session_id}",
            f"status={self.status}",
            f"source_context_ref={self.source_context_ref}",
        ]
        if self.output_context_hash:
            parts.append(f"output_context_hash={self.output_context_hash}")
        return " ".join(parts)


def codex_state_root() -> Path:
    return Path(
        os.environ.get(
            "CODEX_STATE",
            os.path.join(os.environ.get("XDG_STATE_HOME", "~/.local/state"), "codex"),
        )
    ).expanduser()


def sessions_root() -> Path:
    return Path(
        os.environ.get("CODEX_SESSIONS_ROOT", "~/.config/codex/sessions")
    ).expanduser()


def prompt_path() -> Path:
    return codex_state_root() / "meta" / "effective_prompt.txt"


def prjroot() -> Path:
    return Path(os.environ.get("PRJROOT", "~/src")).expanduser()


def session_context_paths() -> SessionContextPaths:
    root = codex_state_root() / "session_context"
    return SessionContextPaths(
        root=root,
        current_context=root / "current" / "session_context.v1.json",
        latest_pointer=root / "latest.json",
        diff_dir=root / "diffs",
        sync_event_dir=root / "sync_events",
        loader_report_dir=root / "loader_reports",
    )


def loader_input_path() -> Path:
    return codex_state_root() / "meta" / "session_context_loader_input.json"


def encode_event_id(trigger: str, event_id: str | None) -> str:
    normalized = normalize_trigger(trigger)
    base = (event_id or "").strip() or str(uuid.uuid4())
    if base.startswith(TRIGGER_PREFIX):
        return base
    return f"{TRIGGER_PREFIX}{normalized}:{base}"


def normalize_trigger(trigger: str | None) -> str:
    normalized = (trigger or "manual").strip().lower()
    if normalized not in SUPPORTED_TRIGGERS:
        raise ValueError(f"unsupported session_context trigger: {trigger}")
    return normalized


def derive_trigger(event_id: str | None) -> str:
    if not event_id:
        return "manual"
    if event_id.startswith(TRIGGER_PREFIX):
        _, _, rest = event_id.partition(TRIGGER_PREFIX)
        trigger, _, _ = rest.partition(":")
        if trigger in SUPPORTED_TRIGGERS:
            return trigger
    return "manual"


def latest_session_file(root: Path) -> Path | None:
    if not root.exists():
        return None
    candidates = [path for path in root.rglob("*.jsonl") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def _truncate(text: str, limit: int = 180) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _load_session_snapshot(
    path: Path | None, max_messages: int = 8
) -> tuple[str, list[str], str | None]:
    if path is None or not path.exists():
        return "session-none", [], None

    session_id = path.stem
    cwd_value: str | None = None
    messages: deque[str] = deque(maxlen=max_messages)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("type") == "session_meta":
                body = payload.get("payload", {})
                if isinstance(body, dict):
                    raw_id = body.get("id")
                    if isinstance(raw_id, str) and raw_id:
                        session_id = raw_id
                    raw_cwd = body.get("cwd")
                    if isinstance(raw_cwd, str) and raw_cwd:
                        cwd_value = raw_cwd
                continue
            if payload.get("type") == "response_item":
                body = payload.get("payload", {})
                if body.get("type") != "message" or body.get("role") != "user":
                    continue
                parts = [
                    str(item.get("text", ""))
                    for item in body.get("content", [])
                    if item.get("type") == "input_text"
                ]
                text = "\n".join(part for part in parts if part.strip())
                normalized = _normalize_text(text)
                if normalized:
                    messages.append(text)
                continue
            if payload.get("type") == "event_msg":
                body = payload.get("payload", {})
                if body.get("type") != "user_message":
                    continue
                text = str(body.get("message", ""))
                normalized = _normalize_text(text)
                if normalized:
                    messages.append(text)
    return session_id, list(messages), cwd_value


def _extract_list_items(messages: list[str], limit: int = 6) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for raw in reversed(messages):
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("-", "*")):
                candidate = stripped[1:].strip()
            elif re.match(r"^\d+\.", stripped):
                candidate = re.sub(r"^\d+\.\s*", "", stripped)
            else:
                continue
            normalized = _truncate(_normalize_text(candidate), 200)
            if normalized and normalized not in seen:
                seen.add(normalized)
                items.append(normalized)
            if len(items) >= limit:
                return items
    return items


def _extract_refs(messages: list[str]) -> tuple[list[str], list[str], list[str]]:
    joined = "\n".join(messages)
    proposal_refs = sorted({match.group(0) for match in PROPOSAL_REF_RE.finditer(joined)})
    backlog_refs = sorted({match.group(0) for match in BACKLOG_REF_RE.finditer(joined)})
    gate_refs = sorted({match.group(0) for match in GATE_REF_RE.finditer(joined)})
    return proposal_refs, backlog_refs, gate_refs


def _active_objectives(messages: list[str], limit: int = 4) -> list[str]:
    objectives: list[str] = []
    for raw in reversed(messages):
        normalized = _normalize_text(raw)
        if not normalized:
            continue
        objectives.append(_truncate(normalized, 180))
        if len(objectives) >= limit:
            break
    return objectives


def _run_git(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if cp.returncode != 0:
        return ""
    return cp.stdout.strip()


def _discover_repo_roots(root: Path) -> list[Path]:
    repos: list[Path] = []
    if (root / ".git").exists():
        repos.append(root)
    if not root.exists():
        return repos
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / ".git").exists():
            repos.append(child)
    return repos


def _repo_state(path: Path) -> dict[str, Any]:
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], path) or None
    commit_hash = _run_git(["rev-parse", "--short", "HEAD"], path)
    commit_ref = f"{path.name}@{commit_hash}" if commit_hash else None
    dirty = bool(_run_git(["status", "--porcelain"], path))
    epoch_raw = _run_git(["log", "-1", "--format=%ct"], path)
    try:
        epoch = int(epoch_raw)
    except ValueError:
        epoch = -1
    return {
        "repo_id": path.name,
        "branch": branch,
        "commit_ref": commit_ref,
        "dirty": dirty,
        "_epoch": epoch,
    }


def _repo_states(root: Path, limit: int = 8) -> list[dict[str, Any]]:
    rows = [_repo_state(path) for path in _discover_repo_roots(root)]
    rows.sort(key=lambda row: (not row["dirty"], -row["_epoch"], row["repo_id"]))
    trimmed = rows[:limit]
    return [
        {
            "repo_id": row["repo_id"],
            "branch": row["branch"],
            "commit_ref": row["commit_ref"],
            "dirty": row["dirty"],
        }
        for row in trimmed
    ]


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash_value(value: Any) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _hash_context(payload: dict[str, Any]) -> str:
    basis = dict(payload)
    basis.pop("context_hash", None)
    return hashlib.sha256(_canonical_json(basis).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_current_session_context() -> dict[str, Any] | None:
    payload = _read_json(session_context_paths().current_context)
    if payload is None:
        return None
    _validate_payload("session_context", payload)
    return payload


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _current_context_source_ref(paths: SessionContextPaths, context_hash: str | None) -> str:
    ref = paths.current_context_ref()
    if context_hash:
        return f"{ref}#context_hash={context_hash}"
    return ref


def _latest_pointer_payload(paths: SessionContextPaths, context_hash: str) -> dict[str, Any]:
    return {
        "kind": "session_context.latest_pointer.v1",
        "generated_at": utc_now(),
        "context_ref": paths.current_context_ref(),
        "context_hash": context_hash,
    }


def build_loader_input() -> dict[str, Any]:
    paths = session_context_paths()
    current = load_current_session_context()
    if current is None:
        return {
            "kind": "session_context.loader_input.internal.v1",
            "generated_at": utc_now(),
            "status": "unavailable",
            "source_context_ref": paths.current_context_ref(),
            "source_context_hash": None,
            "consumed_sections": [],
            "skipped_sections": list(SUMMARY_SECTION_KEYS),
            "evidence_refs": [paths.current_context_ref()],
        }

    consumed_sections = [
        section for section in SUMMARY_SECTION_KEYS if current.get(section)
    ]
    skipped_sections = [
        section for section in SUMMARY_SECTION_KEYS if section not in consumed_sections
    ]
    context_hash = str(current.get("context_hash", "")) or None
    evidence_refs = [paths.current_context_ref(), paths.latest_pointer_ref()]
    return {
        "kind": "session_context.loader_input.internal.v1",
        "generated_at": utc_now(),
        "status": "available",
        "source_context_ref": _current_context_source_ref(paths, context_hash),
        "source_context_hash": context_hash,
        "consumed_sections": consumed_sections,
        "skipped_sections": skipped_sections,
        "evidence_refs": evidence_refs,
        "context": current,
    }


def write_loader_input(path: Path) -> dict[str, Any]:
    payload = build_loader_input()
    _atomic_write_json(path, payload)
    return payload


def load_loader_input(path: Path | None = None) -> dict[str, Any] | None:
    target = path or loader_input_path()
    payload = _read_json(target)
    return payload


def render_loader_input_summary(loader_input: dict[str, Any] | None) -> str:
    if not loader_input:
        return "session_context_carryover:\n- status: unavailable\n- reason: loader input missing\n"

    status = str(loader_input.get("status", "unavailable"))
    lines = ["session_context_carryover:"]
    lines.append(f"- status: {status}")
    if status != "available":
        lines.append(f"- source_context_ref: {loader_input.get('source_context_ref')}")
        return "\n".join(lines) + "\n"

    context = loader_input.get("context")
    if not isinstance(context, dict):
        lines.append("- reason: context payload missing")
        return "\n".join(lines) + "\n"

    lines.append(f"- context_id: {context.get('context_id')}")
    lines.append(f"- generated_at: {context.get('generated_at')}")
    consumed = loader_input.get("consumed_sections", [])
    lines.append(f"- consumed_sections: {', '.join(consumed) if consumed else 'none'}")

    objectives = context.get("active_objectives", [])
    if isinstance(objectives, list):
        for item in objectives[:3]:
            lines.append(f"- objective: {_truncate(_normalize_text(str(item)), 160)}")

    next_steps = context.get("next_steps", [])
    if isinstance(next_steps, list):
        for item in next_steps[:3]:
            lines.append(f"- next_step: {_truncate(_normalize_text(str(item)), 160)}")

    gate_refs = context.get("open_gate_refs", [])
    if isinstance(gate_refs, list) and gate_refs:
        lines.append(f"- open_gates: {', '.join(str(item) for item in gate_refs[:6])}")

    proposal_refs = context.get("proposal_refs", [])
    if isinstance(proposal_refs, list) and proposal_refs:
        lines.append(
            f"- proposal_refs: {', '.join(str(item) for item in proposal_refs[:4])}"
        )

    backlog_refs = context.get("backlog_item_refs", [])
    if isinstance(backlog_refs, list) and backlog_refs:
        lines.append(
            f"- backlog_item_refs: {', '.join(str(item) for item in backlog_refs[:6])}"
        )

    repo_states = context.get("repo_states", [])
    if isinstance(repo_states, list):
        for repo in repo_states[:4]:
            if not isinstance(repo, dict):
                continue
            repo_id = repo.get("repo_id")
            branch = repo.get("branch")
            commit_ref = repo.get("commit_ref")
            dirty = "dirty" if repo.get("dirty") else "clean"
            lines.append(
                f"- repo_state: {repo_id} branch={branch} commit={commit_ref} {dirty}"
            )

    return "\n".join(lines) + "\n"


def _resolve_target_session_id(target_session_id: str | None) -> str:
    if target_session_id:
        normalized = target_session_id.strip()
        if normalized:
            return normalized
    session_file = latest_session_file(sessions_root())
    session_id, _, _ = _load_session_snapshot(session_file)
    normalized = session_id.strip()
    if normalized:
        return normalized
    return "session-unresolved"


def load_fresh_session_context(
    *,
    target_session_id: str | None = None,
    input_path: Path | None = None,
) -> FreshSessionLoadResult:
    paths = session_context_paths()
    loader_input = load_loader_input(input_path)
    if loader_input is None:
        loader_input = build_loader_input()

    status = "failed"
    output_context_hash: str | None = None
    consumed_sections: list[str] = []
    skipped_sections: list[str] = list(SUMMARY_SECTION_KEYS)
    source_context_ref = paths.current_context_ref()
    evidence_refs = [paths.current_context_ref()]

    if loader_input.get("status") == "available":
        source_context_ref = str(loader_input.get("source_context_ref", source_context_ref))
        source_context_hash = loader_input.get("source_context_hash")
        output_context_hash = (
            str(source_context_hash) if isinstance(source_context_hash, str) else None
        )
        consumed_sections = [
            str(item) for item in loader_input.get("consumed_sections", []) if str(item)
        ]
        skipped_sections = [
            str(item) for item in loader_input.get("skipped_sections", []) if str(item)
        ]
        evidence_refs = [
            str(item) for item in loader_input.get("evidence_refs", []) if str(item)
        ] or evidence_refs
        status = "success"
    else:
        source_context_ref = str(loader_input.get("source_context_ref", source_context_ref))
        evidence_refs = [
            str(item) for item in loader_input.get("evidence_refs", []) if str(item)
        ] or evidence_refs

    report = {
        "schema_version": "v1",
        "kind": "fresh_session_loader_report.v1",
        "report_id": f"loader-{uuid.uuid4().hex[:12]}",
        "target_session_id": _resolve_target_session_id(target_session_id),
        "source_context_ref": source_context_ref,
        "loaded_at": utc_now(),
        "status": status,
        "consumed_sections": consumed_sections,
        "skipped_sections": skipped_sections,
        "output_context_hash": output_context_hash,
        "evidence_refs": evidence_refs,
    }
    _validate_payload("fresh_session_loader_report", report)

    report_path = (
        paths.loader_report_dir
        / f"{utc_now().replace(':', '').replace('-', '')}-{report['report_id']}.json"
    )
    _atomic_write_json(report_path, report)
    return FreshSessionLoadResult(
        report_ref=f"CODEX_STATE/session_context/loader_reports/{report_path.name}",
        target_session_id=str(report["target_session_id"]),
        status=str(report["status"]),
        source_context_ref=str(report["source_context_ref"]),
        output_context_hash=(
            str(report["output_context_hash"])
            if isinstance(report["output_context_hash"], str)
            else None
        ),
    )


def _diff_entries(old: Any, new: Any, path: str = "") -> list[dict[str, Any]]:
    if old == new:
        return []
    if isinstance(old, dict) and isinstance(new, dict):
        changes: list[dict[str, Any]] = []
        for key in sorted(set(old) | set(new)):
            child_path = f"{path}/{key}"
            if key not in old:
                changes.append(
                    {
                        "op": "add",
                        "path": child_path,
                        "old_value_hash": None,
                        "new_value_hash": _hash_value(new[key]),
                    }
                )
                continue
            if key not in new:
                changes.append(
                    {
                        "op": "remove",
                        "path": child_path,
                        "old_value_hash": _hash_value(old[key]),
                        "new_value_hash": None,
                    }
                )
                continue
            changes.extend(_diff_entries(old[key], new[key], child_path))
        return changes
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        changes: list[dict[str, Any]] = []
        for index, (old_item, new_item) in enumerate(zip(old, new, strict=False)):
            changes.extend(_diff_entries(old_item, new_item, f"{path}/{index}"))
        if changes:
            return changes
    return [
        {
            "op": "replace",
            "path": path or "/",
            "old_value_hash": _hash_value(old),
            "new_value_hash": _hash_value(new),
        }
    ]


def _build_diff(
    *,
    previous: dict[str, Any],
    current: dict[str, Any],
    context_id: str,
) -> dict[str, Any] | None:
    changes = _diff_entries(previous, current)
    if not changes:
        return None
    added = sum(1 for change in changes if change["op"] == "add")
    removed = sum(1 for change in changes if change["op"] == "remove")
    changed = sum(1 for change in changes if change["op"] == "replace")
    return {
        "schema_version": "v1",
        "kind": "session_context.diff.v1",
        "diff_id": f"diff-{uuid.uuid4().hex[:12]}",
        "context_id": context_id,
        "basis_hash": str(previous.get("context_hash") or ZERO_HASH),
        "candidate_hash": str(current["context_hash"]),
        "generated_at": utc_now(),
        "change_counts": {
            "added": added,
            "removed": removed,
            "changed": changed,
        },
        "changes": changes,
    }


def _source_ref() -> str:
    return "spawn/src/spawn/runtime/session_context_runtime.py"


def build_session_context() -> dict[str, Any]:
    current_sessions_root = sessions_root()
    session_file = latest_session_file(current_sessions_root)
    session_id, messages, session_cwd = _load_session_snapshot(session_file)
    proposal_refs, backlog_refs, gate_refs = _extract_refs(messages)
    paths = session_context_paths()

    context_id = f"ctx-{hashlib.sha256(session_id.encode('utf-8')).hexdigest()[:16]}"
    artifact_refs = [
        ref
        for ref in [
            str(session_file) if session_file is not None else None,
            str(prompt_path()),
            paths.current_context_ref(),
            paths.latest_pointer_ref(),
        ]
        if ref
    ]
    if session_cwd:
        artifact_refs.append(session_cwd)

    payload: dict[str, Any] = {
        "schema_version": "v1",
        "kind": "session_context.v1",
        "context_id": context_id,
        "session_id": session_id,
        "generated_at": utc_now(),
        "source": "spawn://session-context/reconciler",
        "source_ref": _source_ref(),
        "authority_owner": "spawn",
        "active_objectives": _active_objectives(messages),
        "repo_states": _repo_states(prjroot()),
        "proposal_refs": proposal_refs,
        "backlog_item_refs": backlog_refs,
        "open_gate_refs": gate_refs,
        "next_steps": _extract_list_items(messages),
        "artifact_refs": artifact_refs,
        "context_hash": ZERO_HASH,
    }
    payload["context_hash"] = _hash_context(payload)
    return payload


def _worker_packets_root() -> Path | None:
    explicit = os.environ.get("WORKER_PACKETS_ROOT")
    if explicit:
        candidate = Path(explicit).expanduser()
        return candidate if candidate.exists() else None
    candidate = Path(__file__).resolve().parents[4] / "worker_packets"
    return candidate if candidate.exists() else None


@lru_cache(maxsize=None)
def _validator(schema_name: str) -> Draft202012Validator | None:
    root = _worker_packets_root()
    if root is None:
        return None
    schema_rel = SCHEMA_FILES[schema_name]
    schema_path = root / schema_rel
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _validate_payload(schema_name: str, payload: dict[str, Any]) -> None:
    validator = _validator(schema_name)
    if validator is None:
        return
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    if errors:
        joined = "; ".join(error.message for error in errors)
        raise ValueError(f"{schema_name} validation failed: {joined}")


def reconcile_session_context(
    *,
    request_id: str,
    event_id: str,
) -> SessionContextSyncResult:
    trigger = derive_trigger(event_id)
    paths = session_context_paths()
    previous = _read_json(paths.current_context)
    previous_hash = None
    if previous and isinstance(previous.get("context_hash"), str):
        previous_hash = str(previous["context_hash"])

    current = build_session_context()
    _validate_payload("session_context", current)

    diff_payload: dict[str, Any] | None = None
    diff_path: Path | None = None
    action = "write"
    status = "success"
    reason: str | None = None

    if previous_hash is None:
        action = "write"
        status = "success"
        reason = "initial context write" if previous is None else "recovered invalid prior context"
    elif previous_hash == current["context_hash"]:
        action = "noop"
        status = "noop"
    else:
        action = "reconcile"
        status = "success"
        reason = "authoritative context changed"
        diff_payload = _build_diff(
            previous=previous,
            current=current,
            context_id=current["context_id"],
        )
        if diff_payload is None:
            action = "noop"
            status = "noop"

    if diff_payload is not None:
        _validate_payload("session_context_diff", diff_payload)
        diff_path = paths.diff_dir / f"{utc_now().replace(':', '').replace('-', '')}-{diff_payload['diff_id']}.json"
        _atomic_write_json(diff_path, diff_payload)

    if action != "noop" or not paths.current_context.exists():
        _atomic_write_json(paths.current_context, current)
    _atomic_write_json(
        paths.latest_pointer,
        _latest_pointer_payload(paths, str(current["context_hash"])),
    )

    sync_event = {
        "schema_version": "v1",
        "kind": "session_context.sync_event.v1",
        "sync_event_id": f"sync-{request_id}",
        "context_id": current["context_id"],
        "surface_ref": paths.current_context_ref(),
        "trigger": trigger,
        "action": action,
        "pre_sync_hash": previous_hash,
        "post_sync_hash": str(current["context_hash"]),
        "diff_ref": paths.diff_ref(diff_path) if diff_path is not None else None,
        "occurred_at": utc_now(),
        "status": status,
        "actor": "spawn",
        "reason": reason,
    }
    if status == "noop":
        sync_event["pre_sync_hash"] = str(current["context_hash"])
        sync_event["post_sync_hash"] = str(current["context_hash"])
        sync_event["diff_ref"] = None
    _validate_payload("session_context_sync_event", sync_event)

    sync_path = paths.sync_event_dir / f"{utc_now().replace(':', '').replace('-', '')}-{request_id}.json"
    _atomic_write_json(sync_path, sync_event)
    return SessionContextSyncResult(
        trigger=trigger,
        current_ref=paths.current_context_ref(),
        latest_ref=paths.latest_pointer_ref(),
        sync_event_ref=paths.sync_event_ref(sync_path),
        diff_ref=paths.diff_ref(diff_path) if diff_path is not None else None,
        status=status,
        action=action,
        context_hash=str(current["context_hash"]),
    )
