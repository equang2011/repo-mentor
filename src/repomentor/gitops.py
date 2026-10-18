"""Upstream repository cache and tree export.

Each upstream repo is kept as one bare clone under $REPOMENTOR_HOME/repos/. Trees are
exported with read-tree + checkout-index into a throwaway index rather than with
`git archive`: archive honors `export-ignore` attributes (which can silently drop test
files), and checkout-index gives exactly what a normal checkout would. core.autocrlf is
forced off so files are byte-identical to upstream regardless of the user's git config.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from repomentor import paths, proc
from repomentor.errors import ToolError

_GIT_CFG = ["-c", "core.autocrlf=false", "-c", "core.safecrlf=false", "-c", "core.longpaths=true"]


def git(*args: str | Path, cwd: Path | None = None, timeout: float = 300, check: bool = True, env=None):
    proc.require_tool("git")
    return proc.run(["git", *_GIT_CFG, *args], cwd=cwd, timeout=timeout, check=check, env=env, what="git")


def cache_path(url: str) -> Path:
    name = re.sub(r"\.git$", "", url.rstrip("/").split("/")[-1]) or "repo"
    owner = url.rstrip("/").split("/")[-2] if url.count("/") >= 2 else "local"
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{owner}__{name}")
    return paths.repo_cache_dir() / f"{safe}.git"


def has_commit(bare: Path, sha: str) -> bool:
    return git("cat-file", "-e", f"{sha}^{{commit}}", cwd=bare, check=False).ok


def ensure_repo(url: str, shas: list[str]) -> Path:
    """Return a bare clone containing every sha, cloning or fetching as needed."""
    bare = cache_path(url)
    if not bare.exists():
        bare.parent.mkdir(parents=True, exist_ok=True)
        result = git("clone", "--bare", "--quiet", url, bare, timeout=900, check=False)
        if not result.ok:
            raise ToolError(f"could not clone {url} (network needed on first use):\n{result.tail()}")
    missing = [s for s in shas if not has_commit(bare, s)]
    if missing:
        git("fetch", "--quiet", "origin", "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*",
            cwd=bare, timeout=900, check=False)
        for sha in missing:
            if not has_commit(bare, sha):
                git("fetch", "--quiet", "origin", sha, cwd=bare, timeout=900, check=False)
        still = [s for s in shas if not has_commit(bare, s)]
        if still:
            raise ToolError(f"commit(s) {', '.join(still)} not found in {url}")
    return bare


def parents(bare: Path, sha: str) -> list[str]:
    out = git("rev-list", "--parents", "-n", "1", sha, cwd=bare).stdout.split()
    return out[1:]


def export_tree(bare: Path, sha: str, dest: Path) -> None:
    """Write the tree of `sha` into `dest` (created; must not exist) with no .git."""
    dest.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="repomentor-idx-") as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        git("--git-dir", bare, "--work-tree", dest, "read-tree", sha, env=env)
        git("--git-dir", bare, "--work-tree", dest, "checkout-index", "--all", "--force", env=env, timeout=600)


def apply_patch(tree: Path, patch: Path, reverse: bool = False) -> None:
    args = ["apply", "--whitespace=nowarn"] + (["-R"] if reverse else []) + [str(patch.resolve())]
    result = git(*args, cwd=tree, check=False)
    if not result.ok:
        raise ToolError(f"could not apply {patch.name}:\n{result.tail()}")


def diff_source(bare: Path, buggy: str, fixed: str, test_paths: list[str]) -> str:
    excludes = [f":(exclude){p}" for p in test_paths]
    return git("diff", "--no-color", buggy, fixed, "--", *excludes, cwd=bare).stdout


def init_snapshot(repo: Path) -> None:
    """git init + one 'Initial snapshot' commit, independent of the user's git identity."""
    git("init", "--quiet", "-b", "main", cwd=repo)
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("*.egg-info/\n__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    git("add", "--all", cwd=repo, timeout=600)
    git(
        "-c", "user.name=RepoMentor", "-c", "user.email=repomentor@localhost", "-c", "commit.gpgsign=false",
        "commit", "--quiet", "--no-verify", "-m", "Initial snapshot",
        cwd=repo, timeout=600,
    )


def commit_count(repo: Path) -> int:
    return int(git("rev-list", "--count", "HEAD", cwd=repo).stdout.strip())
