#!/usr/bin/env python3
"""Check and optionally fix missing module docstrings in src/spawn."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "spawn"


def iter_targets() -> list[Path]:
    out: list[Path] = []
    for path in sorted(SRC.rglob("*.py")):
        # Generated gRPC code is excluded from docstring policy.
        if "/v1/" in path.as_posix():
            continue
        out.append(path)
    return out


def default_docstring(path: Path) -> str:
    rel = path.relative_to(SRC).with_suffix("")
    module = ".".join(rel.parts)
    return f'"""Module `{module}`."""\n\n'


def has_module_docstring(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return False
    doc = ast.get_docstring(tree)
    return bool(doc and doc.strip())


def fix_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(default_docstring(path) + text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true", help="Insert generated docstrings when missing.")
    args = parser.parse_args()

    missing: list[Path] = [p for p in iter_targets() if not has_module_docstring(p)]
    if not missing:
        print("docstrings-sync: ok")
        return 0

    if args.fix:
        for path in missing:
            fix_file(path)
            print(f"fixed: {path.relative_to(ROOT)}")
        print(f"docstrings-sync: fixed {len(missing)} file(s)")
        return 0

    for path in missing:
        print(f"missing module docstring: {path.relative_to(ROOT)}")
    print(f"docstrings-sync: {len(missing)} file(s) missing module docstrings")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

