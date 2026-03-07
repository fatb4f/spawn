#!/usr/bin/env python3
"""Smoke-test Codex seed catalog extraction."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, env: dict[str, str]) -> None:
    cp = subprocess.run(
        cmd, cwd=ROOT, env=env, text=True, capture_output=True, check=False
    )
    if cp.returncode != 0:
        raise SystemExit(
            f"command failed ({cp.returncode}): {' '.join(cmd)}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="spawn-seed-catalog-") as td:
        tmp = Path(td)
        history_path = tmp / "history.jsonl"
        sessions_root = tmp / "sessions"
        generated_context = tmp / "generated_prompt_context.txt"
        out_dir = tmp / "out"
        sessions_root.mkdir(parents=True, exist_ok=True)

        history_rows = [
            {
                "session_id": "s1",
                "ts": 1772800000,
                "text": (
                    "Generate context.json and report.md under "
                    "/home/_404/src/proposal_register/state_space"
                ),
            },
            {
                "session_id": "s1",
                "ts": 1772800001,
                "text": "Define a schema contract with required fields and validate against it",
            },
            {
                "session_id": "s1",
                "ts": 1772800002,
                "text": "Run this on .timer and post-commit with a dedicated handler",
            },
        ]
        history_path.write_text(
            "".join(json.dumps(row) + "\n" for row in history_rows), encoding="utf-8"
        )

        session_path = sessions_root / "sample.jsonl"
        session_rows = [
            {
                "timestamp": "2026-03-06T23:00:00Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Create SKILL.md with allowed-tools and scripts/ references/"
                            ),
                        }
                    ],
                },
            }
        ]
        session_path.write_text(
            "".join(json.dumps(row) + "\n" for row in session_rows), encoding="utf-8"
        )

        generated_context.write_text(
            "latest_session_file: /home/_404/.config/codex/sessions/latest.jsonl\n",
            encoding="utf-8",
        )

        env = os.environ.copy()
        run(
            [
                "uv",
                "run",
                "spawnctl",
                "ssot",
                "extract-codex-seeds",
                "--history-path",
                str(history_path),
                "--sessions-root",
                str(sessions_root),
                "--generated-context",
                str(generated_context),
                "--out-dir",
                str(out_dir),
            ],
            env=env,
        )
        run(
            [
                "uv",
                "run",
                "spawnctl",
                "ssot",
                "validate-file",
                "seed.catalog",
                str(out_dir / "codex-seed-catalog.json"),
            ],
            env=env,
        )

        catalog = json.loads((out_dir / "codex-seed-catalog.json").read_text())
        counts = {
            item["target_schema_name"]: item["hit_count"]
            for item in catalog["seed_candidates"]
        }
        assert counts["artifact.spec"] > 0
        assert counts["schema.contract"] > 0
        assert counts["trigger.spec"] > 0

    print("seed-catalog-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
