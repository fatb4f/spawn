#!/usr/bin/env python3
"""Shared runtime context resolver for watcher scripts.

This module resolves effective user/host and key path roots using:
1) explicit environment overrides
2) dotfiles chezmoi data overrides (if available)
3) current process user/hostname
"""

from __future__ import annotations

import getpass
import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path


_KV_RE = re.compile(r'^\s*([A-Za-z0-9_]+)\s*:\s*"?([^"]*)"?\s*$')


def _extract_dotfiles_block(path: Path) -> dict[str, str]:
    if not path.exists() or not path.is_file():
        return {}
    out: dict[str, str] = {}
    in_dotfiles = False
    dotfiles_indent = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if stripped == "dotfiles:":
            in_dotfiles = True
            dotfiles_indent = indent
            continue
        if not in_dotfiles:
            continue
        if indent <= dotfiles_indent:
            break
        m = _KV_RE.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


@dataclass(frozen=True)
class RuntimeContext:
    user: str
    host: str
    home: Path
    dotfiles_source_dir: Path
    codex_home: Path
    codex_state: Path
    codex_config_path: Path
    codex_sessions_root: Path
    noctalia_settings_target: Path
    noctalia_settings_source_legacy: Path


def load_runtime_context() -> RuntimeContext:
    env_user = os.environ.get("WATCH_EFFECTIVE_USER", "").strip()
    env_host = os.environ.get("WATCH_EFFECTIVE_HOST", "").strip()

    current_user = getpass.getuser()
    current_host = socket.gethostname()
    current_home = Path.home()

    dotfiles_source_dir = current_home / "src" / "dotfiles"
    base_data = _extract_dotfiles_block(dotfiles_source_dir / ".chezmoidata.yaml")
    local_data = _extract_dotfiles_block(dotfiles_source_dir / ".chezmoidata" / "99-local-overrides.yaml")

    data_user = (local_data.get("userOverride", "") or base_data.get("userOverride", "")).strip()
    data_host = (local_data.get("hostOverride", "") or base_data.get("hostOverride", "")).strip()

    effective_user = env_user or data_user or current_user
    effective_host = env_host or data_host or current_host
    effective_home = Path("/home") / effective_user

    return RuntimeContext(
        user=effective_user,
        host=effective_host,
        home=effective_home,
        dotfiles_source_dir=Path("/home") / effective_user / "src" / "dotfiles",
        codex_home=Path("/home") / effective_user / ".config" / "codex",
        codex_state=Path("/home") / effective_user / ".local" / "state" / "codex",
        codex_config_path=Path("/home") / effective_user / ".config" / "codex" / "config.toml",
        codex_sessions_root=Path("/home") / effective_user / ".config" / "codex" / "sessions",
        noctalia_settings_target=Path("/home") / effective_user / ".config" / "noctalia" / "settings.json",
        noctalia_settings_source_legacy=Path("/home")
        / effective_user
        / "src"
        / "dotfiles"
        / "dot_config"
        / "noctalia"
        / "settings.json",
    )
