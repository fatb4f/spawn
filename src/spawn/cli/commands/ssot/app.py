"""SSOT validation command group."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from spawn.cli.shared import console
from spawn.ssot.registry import schema_registry
from spawn.ssot.validate import validate_payload

app = typer.Typer(help="SSOT schema helpers")


@app.command("list")
def list_schemas() -> None:
    rows = [
        {
            "name": item.name,
            "version": item.version,
            "file": item.file,
            "canonical": item.canonical,
        }
        for item in schema_registry.list_schemas()
    ]
    console.print_json(json.dumps(rows, sort_keys=True))


@app.command("validate-file")
def validate_file(
    schema_name: str = typer.Argument(..., help="Schema name from schema.index.json"),
    path: str = typer.Argument(..., help="Path to JSON payload file"),
    version: str = typer.Option("v1", "--version"),
) -> None:
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    errors = validate_payload(schema_name=schema_name, version=version, payload=payload)
    if errors:
        console.print_json(json.dumps({"ok": False, "errors": errors}, sort_keys=True))
        raise typer.Exit(1)
    console.print_json(json.dumps({"ok": True, "errors": []}, sort_keys=True))


@app.command("validate-json")
def validate_json(
    schema_name: str = typer.Argument(..., help="Schema name from schema.index.json"),
    version: str = typer.Option("v1", "--version"),
) -> None:
    raw = sys.stdin.read()
    payload = json.loads(raw)
    errors = validate_payload(schema_name=schema_name, version=version, payload=payload)
    if errors:
        console.print_json(json.dumps({"ok": False, "errors": errors}, sort_keys=True))
        raise typer.Exit(1)
    console.print_json(json.dumps({"ok": True, "errors": []}, sort_keys=True))

