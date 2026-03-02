#!/usr/bin/env python3
"""Generate gRPC Python stubs from canonical proto specs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTO_ROOT = ROOT / "api" / "proto"
PROTO_FILES = [
    PROTO_ROOT / "spawn" / "v1" / "spawn_control.proto",
]
OUT = ROOT / "src"


def main() -> int:
    missing = [str(p) for p in PROTO_FILES if not p.exists()]
    if missing:
        raise SystemExit(f"missing proto files: {', '.join(missing)}")

    args = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{PROTO_ROOT}",
        f"--python_out={OUT}",
        f"--grpc_python_out={OUT}",
        *[str(p) for p in PROTO_FILES],
    ]
    subprocess.run(args, check=True)
    for p in PROTO_FILES:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
