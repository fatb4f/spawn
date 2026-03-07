"""Codex-backed structured seed extraction helpers."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xdg_base_dirs import xdg_state_home

from spawn.ssot.validate import validate_or_raise


DEFAULT_HISTORY_PATH = Path.home() / ".config" / "codex" / "history.jsonl"
DEFAULT_SESSIONS_ROOT = Path.home() / ".config" / "codex" / "sessions"
DEFAULT_GENERATED_CONTEXT = (
    Path.home() / ".local" / "state" / "codex" / "meta" / "generated_prompt_context.txt"
)
DEFAULT_CACHE_PATH = Path.home() / ".cache" / "codex"


@dataclass(frozen=True)
class SeedRule:
    target_schema_name: str
    why_structurable: str
    candidate_fields: tuple[str, ...]
    pattern: re.Pattern[str]


SEED_RULES: tuple[SeedRule, ...] = (
    SeedRule(
        target_schema_name="artifact.spec",
        why_structurable=(
            "Concrete artifact requests recur with explicit path, output format, "
            "and purpose, so they can be normalized into artifact descriptors."
        ),
        candidate_fields=(
            "artifact_id",
            "path",
            "format",
            "purpose",
            "producer",
            "consumer",
            "authority_level",
        ),
        pattern=re.compile(
            r"/home/_404/|~/(src|\.config|\.local)|\b(generate|write|output)\b.+\b(json|jsonl|md|yaml|toml)\b|"
            r"\bto\s+[\"']?/home/_404/",
            re.IGNORECASE,
        ),
    ),
    SeedRule(
        target_schema_name="schema.contract",
        why_structurable=(
            "Schema-first and contract-first requests recur with explicit required "
            "fields and validation behavior."
        ),
        candidate_fields=(
            "schema_name",
            "schema_version",
            "required_fields",
            "validation_rule",
            "authoritative_source",
        ),
        pattern=re.compile(
            r"\b(ssot|json schema|json-schema|schema contract|required fields|schema_version|"
            r"contract-level|validate against)\b",
            re.IGNORECASE,
        ),
    ),
    SeedRule(
        target_schema_name="trigger.spec",
        why_structurable=(
            "Automation is repeatedly expressed as stable event or cadence trigger "
            "definitions."
        ),
        candidate_fields=(
            "trigger_kind",
            "source_event",
            "cadence_or_edge",
            "handler",
            "execution_mode",
            "debounce_policy",
        ),
        pattern=re.compile(
            r"\b(\.timer|\.path|\.socket|pre-commit|post-commit|session-start|session-end|"
            r"session_start|session_end|resume hook|triggered by|on-demand)\b",
            re.IGNORECASE,
        ),
    ),
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def default_output_dir() -> Path:
    state_dir = os.environ.get("STATE_DIRECTORY", "").strip()
    if state_dir:
        return Path(state_dir).expanduser() / "seed-candidates"
    return xdg_state_home() / "spawn" / "seed-candidates"


def _iter_history_messages(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8", errors="replace") as handle:
        for lineno, line in enumerate(handle, 1):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = _normalize_text(str(payload.get("text", "")))
            if not text:
                continue
            raw_ts = payload.get("ts")
            ts = ""
            if isinstance(raw_ts, (int, float)):
                ts = datetime.fromtimestamp(raw_ts, tz=timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                )
            rows.append(
                {
                    "timestamp": ts,
                    "source": "history",
                    "ref": f"{path}:{lineno}",
                    "excerpt": text,
                }
            )
    return rows


def _iter_session_messages(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not root.exists():
        return rows
    for path in sorted(root.rglob("*.jsonl")):
        with path.open(encoding="utf-8", errors="replace") as handle:
            for lineno, line in enumerate(handle, 1):
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                timestamp = str(payload.get("timestamp", ""))
                if payload.get("type") == "response_item":
                    body = payload.get("payload", {})
                    if body.get("type") != "message" or body.get("role") != "user":
                        continue
                    parts = [
                        str(item.get("text", ""))
                        for item in body.get("content", [])
                        if item.get("type") == "input_text"
                    ]
                    text = _normalize_text(" ".join(parts))
                    if not text:
                        continue
                    rows.append(
                        {
                            "timestamp": timestamp,
                            "source": "session_user",
                            "ref": f"{path}:{lineno}",
                            "excerpt": text,
                        }
                    )
                    continue
                if payload.get("type") == "event_msg":
                    body = payload.get("payload", {})
                    if body.get("type") != "user_message":
                        continue
                    text = _normalize_text(str(body.get("message", "")))
                    if not text:
                        continue
                    rows.append(
                        {
                            "timestamp": timestamp,
                            "source": "session_user_event",
                            "ref": f"{path}:{lineno}",
                            "excerpt": text,
                        }
                    )
    return rows


def _iter_generated_context(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        text = _normalize_text(line)
        if not text:
            continue
        rows.append(
            {
                "timestamp": "",
                "source": "generated_context",
                "ref": f"{path}:{lineno}",
                "excerpt": text,
            }
        )
    return rows


def _unique_messages(records: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for record in records:
        key = record["excerpt"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def build_codex_seed_catalog(
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    sessions_root: Path = DEFAULT_SESSIONS_ROOT,
    generated_context_path: Path = DEFAULT_GENERATED_CONTEXT,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> dict[str, Any]:
    raw_records = [
        *_iter_history_messages(history_path),
        *_iter_session_messages(sessions_root),
        *_iter_generated_context(generated_context_path),
    ]
    unique_records = _unique_messages(raw_records)

    seed_candidates: list[dict[str, Any]] = []
    for rule in SEED_RULES:
        sample_evidence = [
            record
            for record in unique_records
            if rule.pattern.search(record["excerpt"])
        ][:8]
        seed_candidates.append(
            {
                "target_schema_name": rule.target_schema_name,
                "why_structurable": rule.why_structurable,
                "candidate_fields": list(rule.candidate_fields),
                "hit_count": sum(
                    1
                    for record in unique_records
                    if rule.pattern.search(record["excerpt"])
                ),
                "sample_evidence": sample_evidence,
            }
        )

    catalog = {
        "schema_name": "seed.catalog",
        "schema_version": "v1",
        "generated_at_utc": _utc_now(),
        "source_kind": "codex",
        "inputs": {
            "history_path": str(history_path),
            "sessions_root": str(sessions_root),
            "generated_context_path": str(generated_context_path),
            "cache_present": cache_path.exists(),
        },
        "stats": {
            "raw_messages": len(raw_records),
            "unique_messages": len(unique_records),
        },
        "seed_candidates": seed_candidates,
    }
    validate_or_raise("seed.catalog", catalog)
    return catalog


def render_seed_catalog_markdown(catalog: dict[str, Any]) -> str:
    lines = [
        "# Codex Structured Seed Candidates",
        "",
        f"- Generated: `{catalog['generated_at_utc']}`",
        f"- Unique normalized messages: `{catalog['stats']['unique_messages']}`",
        f"- Cache present: `{catalog['inputs']['cache_present']}`",
        "",
        "## Summary",
        "",
        "| Target Schema | Hits | Why |",
        "|---|---:|---|",
    ]
    for item in catalog["seed_candidates"]:
        lines.append(
            f"| {item['target_schema_name']} | {item['hit_count']} | "
            f"{item['why_structurable']} |"
        )

    for item in catalog["seed_candidates"]:
        lines.extend(["", f"## {item['target_schema_name']} ({item['hit_count']})", ""])
        lines.append(f"- Candidate fields: `{', '.join(item['candidate_fields'])}`")
        for evidence in item["sample_evidence"][:4]:
            lines.append(
                f"- `{evidence['timestamp']}` `{evidence['source']}` `{evidence['ref']}`"
            )
            lines.append(f"  - {evidence['excerpt']}")
    lines.append("")
    return "\n".join(lines)


def write_codex_seed_catalog(
    catalog: dict[str, Any], *, out_dir: Path
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "codex-seed-catalog.json"
    md_path = out_dir / "codex-seed-catalog.md"
    json_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_seed_catalog_markdown(catalog) + "\n", encoding="utf-8")
    return json_path, md_path
