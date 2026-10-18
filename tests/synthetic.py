"""A tiny synthetic upstream repo and fake venv installers, so harness tests run offline.

The upstream is a local git repo with a `minicalc` package (src layout) and two commits:
BUGGY (clamp() returns the low bound for values above the range) and FIXED.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from pathlib import Path

from repomentor import envs

PYPROJECT = """\
[build-system]
requires = ["setuptools>=64"]
build-backend = "setuptools.build_meta"

[project]
name = "minicalc"
version = "0.1.0"
"""

BUGGY_SRC = '''\
def clamp(value, low, high):
    """Limit value to the range [low, high]."""
    if value < low:
        return low
    if value > high:
        return low
    return value
'''

FIXED_SRC = BUGGY_SRC.replace("    if value > high:\n        return low", "    if value > high:\n        return high")

EXISTING_TESTS = '''\
from minicalc import clamp


def test_in_range():
    assert clamp(5, 0, 10) == 5


def test_below():
    assert clamp(-3, 0, 10) == 0
'''

PRIVATE_TESTS = '''\
from minicalc import clamp


def test_above_range():
    assert clamp(11, 0, 10) == 10
    assert clamp(99, -5, 7) == 7


def test_guard_in_range_and_below():
    assert clamp(3, 0, 10) == 3
    assert clamp(-1, 0, 10) == 0
'''

TICKET = """\
# clamp() returns the wrong bound

Steps: `clamp(11, 0, 10)` returns 0.

- **AC1:** values above the range return the upper bound.
- **AC2:** values in range and below the range behave as before.
"""


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "user.name=t", "-c", "user.email=t@t", "-c",
         "commit.gpgsign=false", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


def make_upstream(root: Path) -> tuple[str, str, str]:
    """Create the upstream repo. Returns (url, buggy_sha, fixed_sha)."""
    repo = root / "minicalc-upstream"
    (repo / "src" / "minicalc").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pyproject.toml").write_text(PYPROJECT)
    (repo / "CHANGES.md").write_text("# Changes\n\n- 0.1.0: first release\n")
    (repo / "src" / "minicalc" / "__init__.py").write_text(BUGGY_SRC)
    (repo / "tests" / "test_basic.py").write_text(EXISTING_TESTS)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    buggy = _git(repo, "rev-parse", "HEAD")
    (repo / "src" / "minicalc" / "__init__.py").write_text(FIXED_SRC)
    _git(repo, "commit", "-q", "-am", "fix clamp upper bound (fixes #77)")
    fixed = _git(repo, "rev-parse", "HEAD")
    return repo.as_posix(), buggy, fixed


def challenge_manifest(url: str, buggy: str, fixed: str, **overrides) -> dict:
    data = {
        "schema_version": 1,
        "id": "demo-001",
        "kind": "demo",
        "origin": "upstream-fix",
        "public_fields": ["id", "kind", "repo.name", "difficulty", "time_budget_minutes"],
        "repo": {"name": "minicalc", "url": url, "license": "MIT", "source_file_count": 1,
                 "source_count_command": "find src -name '*.py' | wc -l"},
        "package": {"import_name": "minicalc", "version": "0.1.0"},
        "buggy_sha": buggy,
        "fixed_sha": fixed,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "install": {"lock_file": "lock.txt", "pip_args": ["-e", "."]},
        "existing_tests": {"pytest_args": ["tests"], "test_paths": ["tests"], "deselect": [], "timeout_seconds": 120},
        "private_tests": {"file": "private/test_regression.py", "dest": "tests/test_zz_private.py",
                          "timeout_seconds": 120},
        "acceptance_criteria": [
            {"id": "AC1", "text": "Values above the range return the upper bound.", "tests": ["test_above_range"]},
            {"id": "AC2", "text": "In-range and below-range values are unchanged.", "guard": True,
             "tests": ["test_guard_in_range_and_below"]},
        ],
        "difficulty": "easy",
        "time_budget_minutes": 20,
        "upstream": {"issue_url": "https://example.invalid/minicalc/issues/77", "fix_url": None},
        "validation": {"status": "passed"},
    }
    data.update(overrides)
    return data


def write_challenge(root: Path, manifest: dict, private_tests: str = PRIVATE_TESTS) -> Path:
    d = root / manifest["id"]
    (d / "private").mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (d / "ticket.md").write_text(TICKET)
    (d / "lock.txt").write_text("# synthetic: provided by the fake installer\n")
    (d / "private" / "test_regression.py").write_text(private_tests)
    (d / "private" / "solution_notes.md").write_text("clamp returned low instead of high.\n")
    return d


# --- fake installers -------------------------------------------------------

DEV_SITE = sysconfig.get_paths()["purelib"]  # where this test run's pytest is installed


def site_packages(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Lib" / "site-packages"
    return venv / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"


class FakeEnvs:
    """Replaces pip: the lock 'install' exposes our pytest, the package 'install' a .pth."""

    def __init__(self) -> None:
        self.package_override: Path | None = None  # set to simulate a stale install

    def create_venv(self, venv: Path, python_version: str) -> Path:
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
        return envs.venv_python(venv)

    def install_lock(self, python: Path, lock: Path) -> None:
        venv = python.parent.parent
        (site_packages(venv) / "_fake_lock.pth").write_text(DEV_SITE + "\n")

    def install_package(self, python: Path, repo: Path, pip_args: list[str]) -> None:
        venv = python.parent.parent
        target = self.package_override or repo
        (site_packages(venv) / "_fake_pkg.pth").write_text(str((target / "src").resolve()) + "\n")
