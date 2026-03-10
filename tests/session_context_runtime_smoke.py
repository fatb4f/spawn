#!/usr/bin/env python3
"""Smoke-test session_context runtime reconciliation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from spawn.runtime import session_context_runtime as runtime  # noqa: E402


def run(cmd: list[str], *, cwd: Path) -> None:
    cp = subprocess.run(
        cmd, cwd=cwd, text=True, capture_output=True, check=False
    )
    if cp.returncode != 0:
        raise SystemExit(
            f"command failed ({cp.returncode}): {' '.join(cmd)}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
        )


def append_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    original_env = os.environ.copy()
    try:
        with tempfile.TemporaryDirectory(prefix="spawn-session-context-") as td:
            tmp = Path(td)
            state_root = tmp / "state"
            meta_root = state_root / "meta"
            sessions_root = tmp / "sessions" / "2026" / "03" / "10"
            prjroot = tmp / "repos"
            repo = prjroot / "demo"
            session_file = sessions_root / "sample.jsonl"
            prompt_snippet = meta_root / "generated_prompt_context.txt"
            loader_input = meta_root / "session_context_loader_input.json"

            repo.mkdir(parents=True, exist_ok=True)
            sessions_root.mkdir(parents=True, exist_ok=True)
            meta_root.mkdir(parents=True, exist_ok=True)

            run(["git", "init", "-b", "main"], cwd=repo)
            run(["git", "config", "user.email", "test@example.com"], cwd=repo)
            run(["git", "config", "user.name", "Spawn Test"], cwd=repo)
            (repo / "README.md").write_text("demo\n", encoding="utf-8")
            run(["git", "add", "README.md"], cwd=repo)
            run(["git", "commit", "-m", "init"], cwd=repo)

            append_jsonl(
                session_file,
                [
                    {
                        "timestamp": "2026-03-10T16:00:00Z",
                        "type": "session_meta",
                        "payload": {
                            "id": "session-001",
                            "cwd": str(repo),
                        },
                    },
                    {
                        "timestamp": "2026-03-10T16:01:00Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": (
                                        "Current priority\n"
                                        "- session_context first\n"
                                        "- validate ACM-005 against SCX-005\n"
                                        "Track T030 and proposal_register/session-context/spec_draft.v1.json"
                                    ),
                                }
                            ],
                        },
                    },
                ],
            )

            os.environ.update(
                {
                    "CODEX_STATE": str(state_root),
                    "CODEX_SESSIONS_ROOT": str(tmp / "sessions"),
                    "PRJROOT": str(prjroot),
                    "WORKER_PACKETS_ROOT": str(ROOT.parent / "worker_packets"),
                }
            )

            first = runtime.reconcile_session_context(
                request_id="req-1",
                event_id=runtime.encode_event_id("path", "evt-1"),
            )
            current_path = (
                state_root / "session_context" / "current" / "session_context.v1.json"
            )
            latest_path = state_root / "session_context" / "latest.json"
            sync_dir = state_root / "session_context" / "sync_events"
            diff_dir = state_root / "session_context" / "diffs"

            current_payload = load_json(current_path)
            latest_payload = load_json(latest_path)
            first_sync = load_json(sorted(sync_dir.glob("*.json"))[-1])

            assert first.action == "write"
            assert first.status == "success"
            assert current_payload["session_id"] == "session-001"
            assert (
                "proposal_register/session-context/spec_draft.v1.json"
                in current_payload["proposal_refs"]
            )
            assert "T030" in current_payload["backlog_item_refs"]
            assert "SCX-005" in current_payload["open_gate_refs"]
            assert (
                latest_payload["context_ref"]
                == "CODEX_STATE/session_context/current/session_context.v1.json"
            )
            assert first_sync["trigger"] == "path"
            assert first_sync["action"] == "write"
            assert first_sync["status"] == "success"
            assert list(diff_dir.glob("*.json")) == []

            run(
                [
                    "python",
                    "tools/codex/generate_context.py",
                    "--prjroot",
                    str(prjroot),
                    "--sessions-root",
                    str(tmp / "sessions"),
                    "--output",
                    str(prompt_snippet),
                    "--loader-input-output",
                    str(loader_input),
                ],
                cwd=ROOT,
            )
            prompt_text = prompt_snippet.read_text(encoding="utf-8")
            loader_input_payload = load_json(loader_input)
            assert "session_context_carryover:" in prompt_text
            assert "SCX-005" in prompt_text
            assert loader_input_payload["source_context_hash"] == current_payload["context_hash"]

            append_jsonl(
                session_file,
                [
                    {
                        "timestamp": "2026-03-10T16:02:00Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": (
                                        "Recommended next steps\n"
                                        "1. populate session_context\n"
                                        "2. add timer trigger\n"
                                        "3. keep ACM-005 green"
                                    ),
                                }
                            ],
                        },
                    }
                ],
            )

            second = runtime.reconcile_session_context(
                request_id="req-2",
                event_id=runtime.encode_event_id("timer", "evt-2"),
            )
            second_sync = load_json(sorted(sync_dir.glob("*.json"))[-1])
            diff_files = sorted(diff_dir.glob("*.json"))

            assert second.action == "reconcile"
            assert second.status == "success"
            assert len(diff_files) == 1
            assert second_sync["trigger"] == "timer"
            assert second_sync["action"] == "reconcile"
            assert second_sync["status"] == "success"
            assert second_sync["diff_ref"] is not None

            load_result = runtime.load_fresh_session_context(
                target_session_id="session-002",
                input_path=loader_input,
            )
            report_dir = state_root / "session_context" / "loader_reports"
            loader_report = load_json(sorted(report_dir.glob("*.json"))[-1])
            assert load_result.status == "success"
            assert loader_report["target_session_id"] == "session-002"
            assert loader_report["output_context_hash"] == current_payload["context_hash"]
            assert loader_report["source_context_ref"].endswith(
                f"#context_hash={current_payload['context_hash']}"
            )

            third = runtime.reconcile_session_context(
                request_id="req-3",
                event_id=runtime.encode_event_id("manual", "evt-3"),
            )
            third_sync = load_json(sorted(sync_dir.glob("*.json"))[-1])

            assert third.action == "noop"
            assert third.status == "noop"
            assert len(sorted(diff_dir.glob("*.json"))) == 1
            assert third_sync["trigger"] == "manual"
            assert third_sync["action"] == "noop"
            assert third_sync["status"] == "noop"
            assert third_sync["diff_ref"] is None
    finally:
        os.environ.clear()
        os.environ.update(original_env)

    print("session-context-runtime-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
