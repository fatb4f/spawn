"""Validate Codex config path settings used by resume/context refresh flow."""

from __future__ import annotations

import argparse
import logging
import tomllib
from pathlib import Path

from spawn.logging_utils import configure_logging
from spawn.runtime_context import load_runtime_context

logger = logging.getLogger(__name__)


def fail(msg: str) -> int:
    logger.error(msg)
    return 1


def main() -> int:
    configure_logging(app_name="spawn.codex_config_validate", default_format="json")
    ctx = load_runtime_context()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ctx.codex_config_path))
    args = parser.parse_args()

    cfg_path = Path(args.config).expanduser()
    if not cfg_path.exists():
        return fail(f"missing config: {cfg_path}")

    try:
        cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        return fail(f"invalid config toml: {exc}")

    paths = cfg.get("paths", {})
    default = cfg.get("default", {})

    history_dir = Path(
        str(paths.get("history_dir", "~/.local/state/codex/history"))
    ).expanduser()
    logs_dir = Path(
        str(paths.get("logs_dir", "~/.local/state/codex/logs"))
    ).expanduser()
    prompt_file = Path(
        str(
            default.get(
                "model_instructions_file",
                "~/.local/state/codex/meta/effective_prompt.txt",
            )
        )
    ).expanduser()

    for d in (history_dir, logs_dir, prompt_file.parent):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            return fail(f"path not writable/accessible: {d} ({exc})")
        if not d.is_dir():
            return fail(f"not a directory: {d}")

    if prompt_file.exists() and not prompt_file.is_file():
        return fail(f"prompt path is not file: {prompt_file}")

    test_file = logs_dir / ".spawn_write_test"
    try:
        test_file.write_text("ok\n", encoding="utf-8")
        test_file.unlink(missing_ok=True)
    except Exception as exc:  # pragma: no cover
        return fail(f"log path not writable: {logs_dir} ({exc})")

    logger.info("codex config validate ok", extra={"config_path": str(cfg_path)})
    print("codex-config-validate: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
