"""Append alert rows for Codex-related events."""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

from spawn.contracts.envelopes import make_event_envelope
from spawn.logging_utils import configure_logging

logger = logging.getLogger(__name__)


def main() -> int:
    configure_logging(app_name="spawn.codex_alert_log", default_format="json")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--severity", default="info")
    parser.add_argument("--reason", default="")
    parser.add_argument(
        "--out",
        default="~/.local/state/codex/watcher/codex-alerts.jsonl",
        help="Output JSONL path",
    )
    args = parser.parse_args()

    raw_event = os.environ.get("SPAWN_EVENT_JSON", os.environ.get("WATCH_EVENT_JSON", "{}"))
    topic = os.environ.get("SPAWN_EVENT_TYPE", os.environ.get("WATCH_EVENT_TOPIC", ""))
    profile = os.environ.get("SPAWN_PROFILE", os.environ.get("WATCH_PROFILE", ""))
    try:
        event: dict[str, Any] = json.loads(raw_event)
    except json.JSONDecodeError:
        event = {"raw": raw_event}

    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    row = make_event_envelope(
        event_type="spawn.alert.raised",
        source="spawn.codex-alert-log",
        dedupe_key=f"spawn.alert.raised:{topic or 'generic'}:{args.reason or 'none'}",
        payload={
            "severity": args.severity,
            "reason": args.reason,
            "topic": topic,
            "profile": profile,
            "event": event,
        },
    )
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    logger.info("alert row appended", extra={"out_path": str(out_path), "topic": topic or "unknown"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
