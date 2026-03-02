"""spawnctl CLI app."""

from __future__ import annotations

import typer

from spawn.cli.commands.codex_session.app import app as codex_session_app
from spawn.cli.commands.codex_session.app import internal as codex_session_internal_app
from spawn.cli.commands.daemon.app import app as daemon_app

app = typer.Typer(help="spawnctl user-facing control CLI.")
app.add_typer(daemon_app, name="daemon")
app.add_typer(codex_session_app, name="codex-session")
app.add_typer(codex_session_internal_app, name="__internal")


def main() -> None:
    app()

