#!/usr/bin/env python3
"""Generate local codex prompt context from git repos and session metadata."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoInfo:
    name: str
    path: Path
    epoch: int
    branch: str
    dirty: bool
    commits: list[str]


def run_git(args: list[str], cwd: Path) -> str:
    cp = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    if cp.returncode != 0:
        return ""
    return cp.stdout.strip()


def is_git_repo(path: Path) -> bool:
    return bool(run_git(["rev-parse", "--is-inside-work-tree"], path))


def repo_epoch(path: Path) -> int:
    out = run_git(["log", "-1", "--format=%ct"], path)
    try:
        return int(out)
    except (TypeError, ValueError):
        return -1


def repo_branch(path: Path) -> str:
    out = run_git(["rev-parse", "--abbrev-ref", "HEAD"], path)
    return out or "detached"


def repo_dirty(path: Path) -> bool:
    out = run_git(["status", "--porcelain"], path)
    return bool(out)


def repo_commits(path: Path, max_commits: int, since_epoch: int | None = None) -> list[str]:
    out = run_git(
        [
            "log",
            f"-{max(10, max_commits * 5)}",
            "--date=short",
            "--pretty=format:%ct|%h|%ad|%s",
        ],
        path,
    )
    if not out:
        return []
    rows: list[str] = []
    for line in out.splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        ct_raw, h, d, s = parts
        try:
            ct = int(ct_raw)
        except ValueError:
            continue
        if since_epoch is not None and ct < since_epoch:
            continue
        rows.append(f"{h} {d} {s}")
        if len(rows) >= max_commits:
            break
    return rows


def discover_git_repos(prjroot: Path) -> list[Path]:
    repos: set[Path] = set()
    if not prjroot.exists():
        return []
    for git_dir in prjroot.rglob(".git"):
        if ".worktrees" in git_dir.parts:
            continue
        if git_dir.is_dir():
            repos.add(git_dir.parent.resolve())
    return sorted(repos)


def parse_project_arg(raw: str) -> tuple[str, Path] | None:
    if "=" in raw:
        name, p = raw.split("=", 1)
        name = name.strip()
        p = p.strip()
    else:
        p = raw.strip()
        name = Path(p).name
    if not p:
        return None
    return name or Path(p).name, Path(p).expanduser().resolve()


def session_cwd(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "session_meta":
                    continue
                payload = obj.get("payload")
                if isinstance(payload, dict):
                    cwd = payload.get("cwd")
                    if isinstance(cwd, str) and cwd:
                        return cwd
    except OSError:
        return None
    return None


def latest_session_file(
    sessions_root: Path,
    preferred_cwd: Path,
    min_mtime_epoch: int | None = None,
    max_cwd_probes: int = 40,
) -> Path | None:
    if not sessions_root.exists():
        return None
    candidates: list[tuple[float, Path]] = []
    preferred = str(preferred_cwd.resolve())
    for path in sessions_root.rglob("*.jsonl"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if min_mtime_epoch is not None and mtime < min_mtime_epoch:
            continue
        candidates.append((mtime, path))
    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    latest_path = candidates[0][1]
    for _, path in candidates[: max(1, max_cwd_probes)]:
        cwd = session_cwd(path)
        if cwd == preferred:
            return path
    return latest_path


def build_repo_info(
    path: Path, max_commits: int, since_epoch: int | None = None
) -> RepoInfo | None:
    if not path.exists() or not path.is_dir():
        return None
    if not is_git_repo(path):
        return None
    epoch = repo_epoch(path)
    return RepoInfo(
        name=path.name,
        path=path,
        epoch=epoch,
        branch=repo_branch(path),
        dirty=repo_dirty(path),
        commits=repo_commits(path, max_commits=max_commits, since_epoch=since_epoch),
    )


def format_output(
    repos: list[RepoInfo],
    prjroot: Path,
    sessions_root: Path,
    session_file: Path | None,
    lookback_hours: int,
) -> str:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    lines: list[str] = []
    lines.append("---")
    lines.append("type: codex-context")
    lines.append("version: 1")
    lines.append(f"generated_at: {now}")
    lines.append(f"prjroot: {prjroot}")
    lines.append(f"sessions_root: {sessions_root}")
    lines.append(f"lookback_hours: {lookback_hours}")
    lines.append(f"repo_count: {len(repos)}")
    lines.append("---")
    lines.append("")
    if session_file is not None:
        lines.append(f"latest_session_file: {session_file}")
    else:
        lines.append("latest_session_file: unavailable")
    lines.append("")
    lines.append("recent_repo_activity:")
    if not repos:
        lines.append("- unavailable")
    for repo in repos:
        lines.append(
            f"- {repo.name} ({repo.branch}) dirty={'yes' if repo.dirty else 'no'} path={repo.path}"
        )
        if repo.commits:
            for commit in repo.commits:
                lines.append(f"  * {commit}")
        else:
            lines.append("  * no recent commits")
    lines.append("")
    return "\n".join(lines)


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f"{path.name}.tmp.",
        delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", action="append", default=[])
    parser.add_argument("--prjroot", default=os.environ.get("PRJROOT", "~/src"))
    parser.add_argument(
        "--sessions-root", default=os.environ.get("CODEX_SESSIONS_ROOT", "~/.config/codex/sessions")
    )
    parser.add_argument(
        "--output",
        default=os.environ.get(
            "CODEX_CONTEXT_SNIPPET",
            os.path.expanduser("~/.local/state/codex/meta/generated_prompt_context.txt"),
        ),
    )
    parser.add_argument("--max-repos", type=int, default=8)
    parser.add_argument("--max-commits", type=int, default=5)
    parser.add_argument(
        "--max-session-cwd-probes",
        type=int,
        default=int(os.environ.get("CODEX_CONTEXT_MAX_SESSION_CWD_PROBES", "40")),
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=int(os.environ.get("CODEX_CONTEXT_LOOKBACK_HOURS", "72")),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prjroot = Path(args.prjroot).expanduser().resolve()
    sessions_root = Path(args.sessions_root).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    lookback_hours = max(0, int(args.lookback_hours))
    now_epoch = int(dt.datetime.now(dt.timezone.utc).timestamp())
    since_epoch = now_epoch - (lookback_hours * 3600) if lookback_hours > 0 else None

    candidates: dict[Path, str] = {}
    for raw in args.project:
        parsed = parse_project_arg(raw)
        if parsed is None:
            continue
        name, path = parsed
        candidates[path] = name

    for path in discover_git_repos(prjroot):
        candidates.setdefault(path, path.name)

    repos: list[RepoInfo] = []
    for path in candidates:
        info = build_repo_info(path, max_commits=args.max_commits, since_epoch=since_epoch)
        if info is not None:
            if since_epoch is not None and not info.dirty and info.epoch < since_epoch:
                continue
            repos.append(info)

    repos.sort(key=lambda r: r.epoch, reverse=True)
    repos = repos[: max(1, args.max_repos)]

    session_file = latest_session_file(
        sessions_root,
        preferred_cwd=prjroot,
        min_mtime_epoch=since_epoch,
        max_cwd_probes=max(1, int(args.max_session_cwd_probes)),
    )
    content = format_output(
        repos=repos,
        prjroot=prjroot,
        sessions_root=sessions_root,
        session_file=session_file,
        lookback_hours=lookback_hours,
    )
    write_atomic(output, content)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
