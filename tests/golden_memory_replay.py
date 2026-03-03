#!/usr/bin/env python3
"""Golden replay test for memory snapshots."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "memory_golden"
EXPECTED_DIR = FIXTURE_DIR / "expected"


def run(cmd: list[str], *, env: dict[str, str]) -> None:
    cp = subprocess.run(
        cmd, cwd=ROOT, env=env, text=True, capture_output=True, check=False
    )
    if cp.returncode != 0:
        raise SystemExit(
            f"command failed ({cp.returncode}): {' '.join(cmd)}\nstdout:\n{cp.stdout}\nstderr:\n{cp.stderr}"
        )


def compare_bytes(actual: Path, expected: Path) -> None:
    a = actual.read_bytes()
    b = expected.read_bytes()
    if a != b:
        raise AssertionError(f"mismatch: {actual} != {expected}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="spawn-memory-golden-") as td:
        tmp = Path(td)
        state_root = tmp / "state" / "spawn"
        cache_root = tmp / "cache" / "spawn"
        memory_root = state_root / "memory"
        memory_root.mkdir(parents=True, exist_ok=True)
        (cache_root / "memory").mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            FIXTURE_DIR / "memory.events.jsonl", memory_root / "memory.events.jsonl"
        )

        env = os.environ.copy()
        env["STATE_DIRECTORY"] = str(state_root)
        env["CACHE_DIRECTORY"] = str(cache_root)

        run(["uv", "run", "spawnctl", "memory", "rebuild"], env=env)
        run(["uv", "run", "spawnctl", "memory", "rebuild"], env=env)

        # Schema validation on generated snapshots.
        run(
            [
                "uv",
                "run",
                "spawnctl",
                "ssot",
                "validate-file",
                "memory.accepted",
                str(memory_root / "memory.accepted.json"),
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
                "memory.proposals",
                str(memory_root / "memory.proposals.json"),
            ],
            env=env,
        )

        compare_bytes(
            memory_root / "memory.accepted.json", EXPECTED_DIR / "memory.accepted.json"
        )
        compare_bytes(
            memory_root / "memory.proposals.json",
            EXPECTED_DIR / "memory.proposals.json",
        )
        compare_bytes(
            memory_root / "memory.prompt.txt", EXPECTED_DIR / "memory.prompt.txt"
        )
        compare_bytes(
            cache_root / "memory" / "memory.prompt.txt",
            EXPECTED_DIR / "memory.prompt.cache.txt",
        )

    print("golden-memory-replay: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
