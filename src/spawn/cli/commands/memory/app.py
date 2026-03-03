"""Memory command group."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import typer

from spawn.cli.shared import console
from spawn.memory import service as memory_service

app = typer.Typer(help="Memory ingestion and review commands")


@app.command("ingest")
def ingest(
    sessions_root: str = typer.Option("", "--sessions-root", help="Codex sessions root"),
    request_id: str = typer.Option("", "--request-id"),
) -> None:
    root = Path(sessions_root).expanduser() if sessions_root else None
    rid = request_id or f"mem-{uuid.uuid4().hex[:12]}"
    summary = memory_service.ingest_sessions(session_root=root, request_id=rid)
    console.print_json(json.dumps(summary, sort_keys=True))


@app.command("list")
def list_memory() -> None:
    console.print_json(json.dumps(memory_service.list_memory(), sort_keys=True))


@app.command("proposals")
def proposals() -> None:
    console.print_json(json.dumps(memory_service.list_proposals(), sort_keys=True))


@app.command("accept")
def accept(proposal_id: str = typer.Argument(...)) -> None:
    ok = memory_service.accept_proposal(proposal_id)
    if not ok:
        console.print(f"proposal not found: {proposal_id}", style="red")
        raise typer.Exit(1)
    console.print(proposal_id)


@app.command("reject")
def reject(proposal_id: str = typer.Argument(...)) -> None:
    ok = memory_service.reject_proposal(proposal_id)
    if not ok:
        console.print(f"proposal not found: {proposal_id}", style="red")
        raise typer.Exit(1)
    console.print(proposal_id)


@app.command("deprecate")
def deprecate(memory_id: str = typer.Argument(...)) -> None:
    ok = memory_service.deprecate_memory(memory_id)
    if not ok:
        console.print(f"memory not found: {memory_id}", style="red")
        raise typer.Exit(1)
    console.print(memory_id)


@app.command("render")
def render_prompt() -> None:
    state = memory_service.build_memory_state()
    console.print(memory_service.render_prompt(state), end="")


@app.command("rebuild")
def rebuild() -> None:
    state = memory_service.rebuild_memory()
    console.print_json(
        json.dumps(
            {
                "accepted": len(state.get("memory", [])),
                "proposals": len(state.get("proposals", [])),
                "tombstones": len(state.get("tombstones", [])),
            },
            sort_keys=True,
        )
    )

