"""Directory-tree operations: exporting challenge refs, copying, overlaying, diffing."""

from __future__ import annotations

import difflib
import os
import shutil
import stat
import sys
from pathlib import Path

from repomentor import gitops
from repomentor.challenges import Challenge
from repomentor.models import DiffStats

# Never copied into grading and never counted as a change: VCS data, venvs, caches,
# and build metadata that `pip install -e` writes into the repo.
IGNORED_DIRS = frozenset(
    {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
     ".tox", ".nox", "htmlcov", ".idea", ".vscode", ".hypothesis"}
)
IGNORED_FILES = frozenset({".coverage", ".DS_Store"})


def _ignored_name(name: str, is_dir: bool) -> bool:
    if is_dir:
        return name in IGNORED_DIRS or name.endswith(".egg-info")
    return name in IGNORED_FILES or name.endswith((".pyc", ".pyo"))


def iter_files(root: Path) -> dict[str, Path]:
    """Relative posix path -> absolute path, for every non-ignored file under root."""
    found: dict[str, Path] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not _ignored_name(d, True))
        for name in sorted(filenames):
            if _ignored_name(name, False):
                continue
            full = Path(dirpath) / name
            found[full.relative_to(root).as_posix()] = full
    return found


def copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        ignore=lambda d, names: [n for n in names if _ignored_name(n, (Path(d) / n).is_dir())],
        symlinks=True,
    )


def rmtree(path: Path) -> None:
    """shutil.rmtree that also removes read-only files (git objects on Windows)."""

    def _onerror(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if not path.exists():
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_onerror)
    else:
        shutil.rmtree(path, onerror=_onerror)


def under(rel: str, prefixes: list[str]) -> bool:
    return any(rel == p.rstrip("/") or rel.startswith(p.rstrip("/") + "/") for p in prefixes)


def replace_paths(dst: Path, src: Path, rel_paths: list[str]) -> None:
    """Make each rel path in dst an exact copy of src's (removing it if src lacks it)."""
    for rel in rel_paths:
        target, origin = dst / rel, src / rel
        if target.is_dir():
            rmtree(target)
        elif target.exists():
            target.unlink()
        if origin.is_dir():
            copy_tree(origin, target)
        elif origin.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, target)


def overlay_source(src: Path, dst: Path, test_paths: list[str]) -> None:
    """Make dst's non-test files match src's (copy changed/new, delete removed)."""
    src_files = {k: v for k, v in iter_files(src).items() if not under(k, test_paths)}
    dst_files = {k: v for k, v in iter_files(dst).items() if not under(k, test_paths)}
    for rel in dst_files.keys() - src_files.keys():
        dst_files[rel].unlink()
    for rel, path in src_files.items():
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def export_buggy(challenge: Challenge, bare: Path, dest: Path) -> None:
    m = challenge.manifest
    gitops.export_tree(bare, m.buggy_sha, dest)
    if m.origin == "synthetic":
        gitops.apply_patch(dest, challenge.directory / m.injection_patch)


def export_fixed(challenge: Challenge, bare: Path, dest: Path) -> None:
    gitops.export_tree(bare, challenge.manifest.fixed_sha, dest)


def _text_lines(path: Path) -> list[str] | None:
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    # Line-ending-only changes (an editor converting to CRLF) are not real edits.
    return text.replace("\r\n", "\n").splitlines()


def diff_stats(pristine: Path, candidate: Path, test_paths: list[str]) -> DiffStats:
    before, after = iter_files(pristine), iter_files(candidate)
    changed: list[str] = []
    added = removed = 0
    for rel in sorted(before.keys() | after.keys()):
        a, b = before.get(rel), after.get(rel)
        if a and b and a.read_bytes() == b.read_bytes():
            continue
        old = _text_lines(a) if a else []
        new = _text_lines(b) if b else []
        if old is None or new is None:  # binary
            changed.append(rel)
            continue
        if old == new:
            continue
        changed.append(rel)
        for line in difflib.unified_diff(old, new, lineterm="", n=0):
            if line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1
    return DiffStats(
        files_changed=len(changed),
        lines_added=added,
        lines_removed=removed,
        changed_files=changed,
        tests_modified=any(under(r, test_paths) for r in changed),
        non_source_modified=any(not under(r, test_paths) and not r.endswith(".py") for r in changed),
    )
