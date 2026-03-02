#!/usr/bin/env python3
"""Export canonical JSON Schemas from pydantic contract models."""

from __future__ import annotations

import json
from pathlib import Path

from spawn.schema_models import ActionRequestV1, ActionResultV1, EventEnvelopeV1

OUT = Path("api/openapi/schemas")
MODELS = {
    "EventEnvelopeV1": EventEnvelopeV1,
    "ActionRequestV1": ActionRequestV1,
    "ActionResultV1": ActionResultV1,
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        path = OUT / f"{name}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
