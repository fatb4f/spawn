"""SSOT validation command group."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from spawn.cli.shared import console
from spawn.ssot.registry import schema_registry
from spawn.ssot.seeds import (
    DEFAULT_GENERATED_CONTEXT,
    DEFAULT_HISTORY_PATH,
    DEFAULT_SESSIONS_ROOT,
    build_codex_seed_catalog,
    default_output_dir,
    write_codex_seed_catalog,
)
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


@app.command("validate-tree")
def validate_tree() -> None:
    errors = schema_registry.validate_tree()
    if errors:
        console.print_json(json.dumps({"ok": False, "errors": errors}, sort_keys=True))
        raise typer.Exit(1)
    console.print_json(
        json.dumps(
            {
                "ok": True,
                "errors": [],
                "schema_count": len(schema_registry.list_schemas()),
            },
            sort_keys=True,
        )
    )


@app.command("extract-codex-seeds")
def extract_codex_seeds(
    out_dir: str = typer.Option("", "--out-dir", help="Output directory for derived artifacts"),
    history_path: str = typer.Option(
        str(DEFAULT_HISTORY_PATH), "--history-path", help="Codex history.jsonl path"
    ),
    sessions_root: str = typer.Option(
        str(DEFAULT_SESSIONS_ROOT), "--sessions-root", help="Codex sessions root"
    ),
    generated_context_path: str = typer.Option(
        str(DEFAULT_GENERATED_CONTEXT),
        "--generated-context",
        help="Generated prompt context path",
    ),
) -> None:
    catalog = build_codex_seed_catalog(
        history_path=Path(history_path).expanduser(),
        sessions_root=Path(sessions_root).expanduser(),
        generated_context_path=Path(generated_context_path).expanduser(),
    )
    target_dir = Path(out_dir).expanduser() if out_dir else default_output_dir()
    json_path, md_path = write_codex_seed_catalog(catalog, out_dir=target_dir)
    console.print_json(
        json.dumps(
            {
                "ok": True,
                "json_path": str(json_path),
                "md_path": str(md_path),
                "seed_candidates": [
                    {
                        "target_schema_name": item["target_schema_name"],
                        "hit_count": item["hit_count"],
                    }
                    for item in catalog["seed_candidates"]
                ],
            },
            sort_keys=True,
        )
    )
