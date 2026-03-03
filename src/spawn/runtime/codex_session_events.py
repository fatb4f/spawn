"""Emit codex.session.updated envelopes from session file updates."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from spawn.contracts.envelopes import make_event_envelope
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


def emit(path: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    event = make_event_envelope(
        event_type="codex.session.updated",
        source="spawn.codex-session-events",
        dedupe_key=f"codex.session.updated:{path}",
        payload={"path": path, "ts": ts},
    )
    import json

    print(json.dumps(event, sort_keys=True), flush=True)
    logger.debug("session event emitted", extra={"path": path})


def main() -> int:
    configure_logging(app_name="spawn.codex_session_events", default_format="json")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-root", default="~/.config/codex/sessions")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()

    root = Path(args.sessions_root).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    logger.info("watching sessions root", extra={"sessions_root": str(root)})

    last = ""
    while True:
        current = latest_session_file(root)
        if current and current != last:
            emit(current)
            last = current
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
