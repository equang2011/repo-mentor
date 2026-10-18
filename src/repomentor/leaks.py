"""Leak check: a workspace must not reveal history, private files, or upstream references."""

from __future__ import annotations

import re
from pathlib import Path

from repomentor import gitops, trees
from repomentor.challenges import Challenge
from repomentor.errors import ToolError


def upstream_markers(challenge: Challenge) -> list[re.Pattern[str]]:
    m = challenge.manifest
    literals = [m.fixed_sha, m.fixed_sha[:10]]
    literals += [u for u in (m.upstream.issue_url, m.upstream.fix_url) if u]
    patterns = [re.compile(re.escape(s), re.IGNORECASE) for s in literals]
    for url in (m.upstream.issue_url, m.upstream.fix_url):
        found = re.search(r"/(issues|pull)/(\d+)", url or "")
        if found:
            kind, number = found.groups()
            patterns.append(re.compile(rf"{kind}/{number}\b"))
            patterns.append(re.compile(rf"(?<![\w&])#{number}\b"))
    return patterns


def _private_contents(challenge: Challenge) -> dict[bytes, str]:
    files = [challenge.manifest_path] + [p for p in (challenge.directory / "private").rglob("*") if p.is_file()]
    return {p.read_bytes(): p.name for p in files if p.stat().st_size > 0}


def check_workspace(ws: Path, challenge: Challenge) -> list[str]:
    """Return a list of problems (empty means clean)."""
    problems: list[str] = []
    repo = ws / "repo"
    try:
        count = gitops.commit_count(repo)
        if count != 1:
            problems.append(f"workspace git history has {count} commits; expected exactly 1")
    except ToolError as exc:
        problems.append(f"workspace repo is not a git repository with one commit: {exc}")

    private = _private_contents(challenge)
    dest_name = Path(challenge.manifest.private_tests.dest).name
    patterns = upstream_markers(challenge)
    for rel, path in trees.iter_files(ws).items():
        if path.name == dest_name:
            problems.append(f"{rel}: has the private test file's name")
        data = path.read_bytes()
        if data in private:
            problems.append(f"{rel}: identical to private file {private[data]}")
        if b"\0" in data[:8192]:
            continue
        text = data.decode("utf-8", errors="replace")
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                problems.append(f"{rel}: contains upstream reference '{match.group(0)}'")
    return problems
