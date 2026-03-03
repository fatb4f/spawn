"""Collect quick diagnostics for Codex resume/session path issues."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from spawn.contracts.envelopes import utc_now
from spawn.logging_utils import configure_logging

logger = logging.getLogger(__name__)


def latest_session_file(sessions_root: Path) -> str | None:
    files = sorted(
        [p for p in sessions_root.rglob("*.jsonl") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )
    if not files:
        return None
    return str(files[-1])


def main() -> int:
    configure_logging(app_name="spawn.codex_resume_diagnose", default_format="json")
    codex_state = Path(
        os.environ.get("CODEX_STATE", "~/.local/state/codex")
    ).expanduser()
    sessions_root = Path(
        os.environ.get("CODEX_SESSIONS_ROOT", "~/.config/codex/sessions")
    ).expanduser()
    out = codex_state / "meta" / "resume_diagnose.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    raw_event = os.environ.get(
        "SPAWN_EVENT_JSON", os.environ.get("WATCH_EVENT_JSON", "{}")
    )
    try:
        event: dict[str, Any] = json.loads(raw_event)
    except json.JSONDecodeError:
        event = {"raw": raw_event}

    payload = {
        "schema": "spawn_resume_diagnose_v1",
        "observed_at": utc_now(),
        "sessions_root": str(sessions_root),
        "sessions_root_exists": sessions_root.exists(),
        "latest_session_file": latest_session_file(sessions_root)
        if sessions_root.exists()
        else None,
        "event": event,
    }
    out.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("resume diagnose written", extra={"out_path": str(out)})
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
