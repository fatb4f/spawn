"""Memory ingestion, persistence, and replay."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spawn.ssot.validate import validate_or_raise

try:
    from xdg_base_dirs import xdg_cache_home, xdg_state_home
except ImportError:  # pragma: no cover
    xdg_cache_home = None
    xdg_state_home = None


def _xdg_state_home() -> Path:
    if xdg_state_home is not None:
        return xdg_state_home()
    return Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()


def _xdg_cache_home() -> Path:
    if xdg_cache_home is not None:
        return xdg_cache_home()
    return Path(os.environ.get("XDG_CACHE_HOME", "~/.cache")).expanduser()


def _systemd_directory(env_name: str) -> Path | None:
    value = os.environ.get(env_name, "").strip()
    if not value:
        return None
    # systemd may return a colon-separated list; we currently need only the first.
    first = value.split(":", 1)[0].strip()
    if not first:
        return None
    return Path(first).expanduser()


def _state_root() -> Path:
    root = _systemd_directory("STATE_DIRECTORY")
    if root is None:
        root = _xdg_state_home() / "spawn"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cache_root() -> Path:
    root = _systemd_directory("CACHE_DIRECTORY")
    if root is None:
        root = _xdg_cache_home() / "spawn"
    root.mkdir(parents=True, exist_ok=True)
    return root


def memory_dir() -> Path:
    path = _state_root() / "memory"
    path.mkdir(parents=True, exist_ok=True)
    return path


def events_path() -> Path:
    return memory_dir() / "memory.events.jsonl"


def cursor_path() -> Path:
    return memory_dir() / "memory.cursor.json"


def accepted_path() -> Path:
    return memory_dir() / "memory.accepted.json"


def proposals_path() -> Path:
    return memory_dir() / "memory.proposals.json"


def prompt_path() -> Path:
    return memory_dir() / "memory.prompt.txt"


def prompt_cache_path() -> Path:
    path = _cache_root() / "memory" / "memory.prompt.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _hash(parts: list[str]) -> str:
    blob = "|".join(parts).encode("utf-8", errors="replace")
    return hashlib.sha256(blob).hexdigest()


def _line_event_id(path: Path, line_no: int, line: str) -> str:
    return _hash([str(path), str(line_no), line])[:24]


@contextmanager
def _memory_lock():
    lock_path = memory_dir() / ".lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def memory_id(kind: str, value: str) -> str:
    return f"mem-{_hash([kind, value])[:20]}"


def proposal_id(kind: str, value: str, source_ref: str) -> str:
    return f"prop-{_hash([kind, value, source_ref])[:20]}"


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    _atomic_write_text(path, json.dumps(payload, sort_keys=True, indent=2) + "\n")


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
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


def _extract_text(entry: dict[str, Any]) -> str:
    if "content" in entry and isinstance(entry["content"], str):
        return entry["content"]
    msg = entry.get("message")
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            if parts:
                return "\n".join(parts)
    return ""


def _extract_role(entry: dict[str, Any]) -> str:
    role = entry.get("role")
    if isinstance(role, str):
        return role
    msg = entry.get("message")
    if isinstance(msg, dict) and isinstance(msg.get("role"), str):
        return msg["role"]
    return ""


@dataclass
class Candidate:
    kind: str
    claim: str
    value: str
    confidence: float
    source_ref: str
    evidence: list[str]


def _extract_candidates(text: str, source_ref: str) -> list[Candidate]:
    normalized = " ".join(text.strip().split())
    if not normalized:
        return []
    lower = normalized.lower()
    out: list[Candidate] = []
    if lower.startswith("i prefer ") or " i prefer " in f" {lower} ":
        out.append(
            Candidate(
                kind="preference",
                claim=normalized,
                value=normalized,
                confidence=0.92,
                source_ref=source_ref,
                evidence=[normalized[:220]],
            )
        )
    if lower.startswith("i use ") or " i use " in f" {lower} ":
        out.append(
            Candidate(
                kind="workflow",
                claim=normalized,
                value=normalized,
                confidence=0.88,
                source_ref=source_ref,
                evidence=[normalized[:220]],
            )
        )
    if lower.startswith("my name is ") or "my timezone is " in lower:
        out.append(
            Candidate(
                kind="identity",
                claim=normalized,
                value=normalized,
                confidence=0.78,
                source_ref=source_ref,
                evidence=[normalized[:220]],
            )
        )
    if "always" in lower or "never" in lower:
        out.append(
            Candidate(
                kind="constraint",
                claim=normalized,
                value=normalized,
                confidence=0.72,
                source_ref=source_ref,
                evidence=[normalized[:220]],
            )
        )
    return out


def _make_event(
    topic: str,
    request_id: str,
    dedupe_key: str,
    payload: dict[str, Any],
    *,
    payload_schema: str | None = None,
) -> dict[str, Any]:
    if payload_schema:
        validate_or_raise(payload_schema, payload)
    row = {
        "schema_name": "event.envelope",
        "schema_version": "v1",
        "event_id": f"evt-{uuid.uuid4().hex}",
        "request_id": request_id,
        "ts": utc_now(),
        "topic": topic,
        "source": "spawn.memory",
        "run_id": request_id,
        "dedupe_key": dedupe_key,
        "payload": payload,
    }
    validate_or_raise("event.envelope", row)
    return row


def _auto_accept(kind: str, confidence: float) -> bool:
    return kind in {"preference", "workflow"} and confidence >= 0.9


def _default_session_root() -> Path:
    return Path(os.environ.get("CODEX_SESSIONS_ROOT", "~/.config/codex/sessions")).expanduser()


def _default_cursor_state() -> dict[str, Any]:
    return {"schema_name": "memory.cursor", "schema_version": "v1", "files": {}}


def _load_cursor() -> dict[str, Any]:
    path = cursor_path()
    payload = _load_json(path, _default_cursor_state())
    if isinstance(payload, dict) and "schema_name" not in payload and isinstance(payload.get("files"), dict):
        # Backward-compat migration for old cursor format.
        payload = {
            "schema_name": "memory.cursor",
            "schema_version": "v1",
            "files": payload.get("files", {}),
        }
    validate_or_raise("memory.cursor", payload)
    return payload


def _save_cursor(payload: dict[str, Any]) -> None:
    validate_or_raise("memory.cursor", payload)
    _write_json(cursor_path(), payload)


def _iter_new_lines(session_root: Path, cursor: dict[str, Any]):
    files = cursor.setdefault("files", {})
    for path in sorted(session_root.rglob("*.jsonl")):
        key = str(path)
        st = path.stat()
        prev = files.get(key, {})
        prev_inode = int(prev.get("inode", 0))
        prev_offset = int(prev.get("offset", 0))
        latest_event_id = str(prev.get("last_event_id", ""))
        inode = int(st.st_ino)
        size = int(st.st_size)
        offset = prev_offset if prev_inode == inode and prev_offset <= size else 0
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            line_no = 0
            for raw in handle:
                line_no += 1
                line = raw.strip()
                if not line:
                    continue
                line_event_id = _line_event_id(path, line_no, line)
                latest_event_id = line_event_id
                yield path, key, line_no, line, line_event_id
            files[key] = {
                "inode": inode,
                "offset": handle.tell(),
                "updated_at": utc_now(),
                "last_event_id": latest_event_id,
            }


def _load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def ingest_sessions(session_root: Path | None = None, request_id: str | None = None) -> dict[str, int]:
    with _memory_lock():
        rid = request_id or f"mem-{uuid.uuid4().hex[:12]}"
        root = session_root or _default_session_root()
        if not root.exists():
            return {"processed_lines": 0, "events_written": 0, "accepted": 0, "proposals": 0}
        cursor = _load_cursor()

        processed = 0
        events_written = 0
        accepted = 0
        proposals = 0
        out_path = events_path()
        existing_memory = build_memory_state()
        accepted_ids = {item["memory_id"] for item in existing_memory["memory"]}

        for path, _, line_no, line, _ in _iter_new_lines(root, cursor):
            processed += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = _extract_role(row).strip().lower()
            if role != "user":
                continue
            text = _extract_text(row)
            source_ref = f"{path}:{line_no}"
            for cand in _extract_candidates(text, source_ref):
                mid = memory_id(cand.kind, cand.value)
                pid = proposal_id(cand.kind, cand.value, cand.source_ref)
                if mid in accepted_ids:
                    continue

                if _auto_accept(cand.kind, cand.confidence):
                    item = {
                        "memory_id": mid,
                        "id": mid,
                        "kind": cand.kind,
                        "claim": cand.claim,
                        "value": cand.value,
                        "confidence": cand.confidence,
                        "provenance": {"source_ref": cand.source_ref, "evidence": cand.evidence},
                        "first_seen_at": utc_now(),
                        "last_seen_at": utc_now(),
                        "status": "accepted",
                        "tags": [],
                    }
                    payload = {"kind": "memory_patch", "upserts": [item], "deprecations": []}
                    event = _make_event(
                        topic="spawn.memory.patch.applied",
                        request_id=rid,
                        dedupe_key=f"patch:{mid}",
                        payload=payload,
                        payload_schema="memory.patch",
                    )
                    _append_jsonl(out_path, event)
                    accepted_ids.add(mid)
                    accepted += 1
                    events_written += 1
                else:
                    proposal = {
                        "proposal_id": pid,
                        "memory_id": mid,
                        "kind": cand.kind,
                        "claim": cand.claim,
                        "value": cand.value,
                        "confidence": cand.confidence,
                        "source": {"source_ref": cand.source_ref},
                        "evidence": cand.evidence,
                        "proposed_by": "spawn.memory.extractor.v0",
                        "gate_reason": "requires_review",
                        "status": "pending",
                        "created_at": utc_now(),
                    }
                    payload = {"kind": "memory_proposal", "proposal": proposal}
                    event = _make_event(
                        topic="spawn.memory.proposal.created",
                        request_id=rid,
                        dedupe_key=f"proposal:{pid}",
                        payload=payload,
                        payload_schema="memory.proposal",
                    )
                    _append_jsonl(out_path, event)
                    proposals += 1
                    events_written += 1

        _save_cursor(cursor)
        _rebuild_memory_unlocked()
        return {
            "processed_lines": processed,
            "events_written": events_written,
            "accepted": accepted,
            "proposals": proposals,
        }


def build_memory_state() -> dict[str, Any]:
    events = _load_events(events_path())
    accepted: dict[str, dict[str, Any]] = {}
    proposals: dict[str, dict[str, Any]] = {}
    tombstones: list[dict[str, Any]] = []

    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        kind = payload.get("kind")
        if kind == "memory_patch":
            for item in payload.get("upserts", []):
                if isinstance(item, dict) and isinstance(item.get("memory_id"), str):
                    accepted[item["memory_id"]] = item
            for mid in payload.get("deprecations", []):
                if isinstance(mid, str) and mid in accepted:
                    accepted[mid]["status"] = "deprecated"
                    tombstones.append({"memory_id": mid, "reason": "deprecated", "at": event.get("ts", utc_now())})
        elif kind == "memory_proposal":
            proposal = payload.get("proposal")
            if isinstance(proposal, dict) and isinstance(proposal.get("proposal_id"), str):
                proposals[proposal["proposal_id"]] = proposal
        elif kind == "memory_proposal.accepted":
            pid = str(payload.get("proposal_id", ""))
            proposal = proposals.get(pid)
            if proposal:
                proposal["status"] = "accepted"
                proposal["reviewed_at"] = event.get("ts", utc_now())
        elif kind == "memory_proposal.rejected":
            pid = str(payload.get("proposal_id", ""))
            proposal = proposals.get(pid)
            if proposal:
                proposal["status"] = "rejected"
                proposal["reviewed_at"] = event.get("ts", utc_now())

    return {
        "schema_name": "memory",
        "schema_version": "v1",
        "memory": sorted(accepted.values(), key=lambda x: (x.get("kind", ""), x.get("value", ""))),
        "proposals": sorted(proposals.values(), key=lambda x: x.get("created_at", "")),
        "tombstones": tombstones,
    }


def render_prompt(memory_state: dict[str, Any]) -> str:
    lines = []
    for item in memory_state.get("memory", []):
        if item.get("status") != "accepted":
            continue
        claim = str(item.get("claim", "")).strip()
        if claim:
            lines.append(f"- {claim}")
    lines = sorted(set(lines))
    return "\n".join(lines) + ("\n" if lines else "")


def _rebuild_memory_unlocked() -> dict[str, Any]:
    state = build_memory_state()
    validate_or_raise("memory", state)
    accepted_payload = {"schema_name": "memory.accepted", "schema_version": "v1", "items": state["memory"]}
    validate_or_raise("memory.accepted", accepted_payload)
    _write_json(accepted_path(), accepted_payload)

    proposals_payload = {"schema_name": "memory.proposals", "schema_version": "v1", "items": state["proposals"]}
    validate_or_raise("memory.proposals", proposals_payload)
    _write_json(proposals_path(), proposals_payload)

    rendered = render_prompt(state)
    _atomic_write_text(prompt_path(), rendered)
    _atomic_write_text(prompt_cache_path(), rendered)
    return state


def rebuild_memory() -> dict[str, Any]:
    with _memory_lock():
        return _rebuild_memory_unlocked()


def list_memory() -> list[dict[str, Any]]:
    state = build_memory_state()
    return [item for item in state["memory"] if item.get("status") == "accepted"]


def list_proposals() -> list[dict[str, Any]]:
    state = build_memory_state()
    return [item for item in state["proposals"] if item.get("status") == "pending"]


def _append_control_event(topic: str, request_id: str, payload: dict[str, Any], dedupe_key: str) -> None:
    payload_schema = None
    kind = str(payload.get("kind", ""))
    if kind == "memory_patch":
        payload_schema = "memory.patch"
    elif kind == "memory_proposal":
        payload_schema = "memory.proposal"
    event = _make_event(
        topic=topic,
        request_id=request_id,
        payload=payload,
        dedupe_key=dedupe_key,
        payload_schema=payload_schema,
    )
    _append_jsonl(events_path(), event)


def accept_proposal(proposal_id_value: str, request_id: str | None = None) -> bool:
    with _memory_lock():
        state = build_memory_state()
        proposal = next((p for p in state["proposals"] if p.get("proposal_id") == proposal_id_value), None)
        if not proposal:
            return False
        rid = request_id or f"mem-{uuid.uuid4().hex[:12]}"
        item = {
            "memory_id": proposal["memory_id"],
            "id": proposal["memory_id"],
            "kind": proposal["kind"],
            "claim": proposal["claim"],
            "value": proposal["value"],
            "confidence": proposal["confidence"],
            "provenance": {"source": proposal.get("source", {}), "evidence": proposal.get("evidence", [])},
            "first_seen_at": proposal.get("created_at", utc_now()),
            "last_seen_at": utc_now(),
            "status": "accepted",
            "tags": [],
        }
        _append_control_event(
            topic="spawn.memory.patch.applied",
            request_id=rid,
            dedupe_key=f"accept:{proposal_id_value}",
            payload={"kind": "memory_patch", "upserts": [item], "deprecations": []},
        )
        _append_control_event(
            topic="spawn.memory.proposal.accepted",
            request_id=rid,
            dedupe_key=f"proposal-accepted:{proposal_id_value}",
            payload={"kind": "memory_proposal.accepted", "proposal_id": proposal_id_value},
        )
        _rebuild_memory_unlocked()
        return True


def reject_proposal(proposal_id_value: str, request_id: str | None = None) -> bool:
    with _memory_lock():
        state = build_memory_state()
        proposal = next((p for p in state["proposals"] if p.get("proposal_id") == proposal_id_value), None)
        if not proposal:
            return False
        rid = request_id or f"mem-{uuid.uuid4().hex[:12]}"
        _append_control_event(
            topic="spawn.memory.proposal.rejected",
            request_id=rid,
            dedupe_key=f"proposal-rejected:{proposal_id_value}",
            payload={"kind": "memory_proposal.rejected", "proposal_id": proposal_id_value},
        )
        _rebuild_memory_unlocked()
        return True


def deprecate_memory(memory_id_value: str, request_id: str | None = None) -> bool:
    with _memory_lock():
        state = build_memory_state()
        found = any(item.get("memory_id") == memory_id_value for item in state["memory"])
        if not found:
            return False
        rid = request_id or f"mem-{uuid.uuid4().hex[:12]}"
        _append_control_event(
            topic="spawn.memory.patch.applied",
            request_id=rid,
            dedupe_key=f"deprecate:{memory_id_value}",
            payload={"kind": "memory_patch", "upserts": [], "deprecations": [memory_id_value]},
        )
        _rebuild_memory_unlocked()
        return True
