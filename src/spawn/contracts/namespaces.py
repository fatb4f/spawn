"""Event namespace definitions for spawn contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CodexNamespaces:
    session: str = "codex.session"
    config: str = "codex.config"
    session_meta: str = "codex.session.meta"
    session_resume: str = "codex.session.resume"
    session_service: str = "codex.session.service"


CODEX = CodexNamespaces()


def event_type(namespace: str, action: str) -> str:
    return f"{namespace}.{action}"


def namespace_of(event_name: str) -> str:
    parts = event_name.split(".")
    if len(parts) < 2:
        return event_name
    return ".".join(parts[:2])
