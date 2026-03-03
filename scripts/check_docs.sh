#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

./scripts/gen_docs.sh
git diff --exit-code docs/api

echo "check-docs: clean"
