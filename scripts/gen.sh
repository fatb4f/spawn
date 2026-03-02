#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Canonical contract sources (hand-edited):
# - api/proto/spawn/v1/spawn_control.proto
# - src/spawn/schema_models.py
test -f api/proto/spawn/v1/spawn_control.proto
test -f src/spawn/schema_models.py

uv run --with grpcio-tools python scripts/gen_grpc.py
PYTHONPATH=src uv run python scripts/export_schemas.py

echo "gen: ok"
