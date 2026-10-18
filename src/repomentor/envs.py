"""Finding the right Python and building per-challenge virtualenvs from the lock file."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from repomentor import proc
from repomentor.errors import ToolError, WorkspaceError

PIP_TIMEOUT = 900


def venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def find_python(version: str) -> str:
    """An interpreter for `version` ("3.13"): this one if it matches, else py/pythonX.Y."""
    if f"{sys.version_info.major}.{sys.version_info.minor}" == version:
        return sys.executable
    if os.name == "nt" and shutil.which("py"):
        result = proc.run(["py", f"-{version}", "-c", "import sys; print(sys.executable)"], timeout=60)
        if result.ok and result.stdout.strip():
            return result.stdout.strip()
    exe = shutil.which(f"python{version}")
    if exe:
        return exe
    raise ToolError(
        f"Python {version} is required by this challenge but was not found "
        f"(tried the current interpreter, 'py -{version}', and 'python{version}'). Install it and retry."
    )


def create_venv(venv: Path, python_version: str) -> Path:
    python = find_python(python_version)
    result = proc.run([python, "-m", "venv", venv], timeout=300)
    if not result.ok:
        raise ToolError(f"could not create a virtualenv at {venv}:\n{result.tail()}")
    return venv_python(venv)


def install_lock(python: Path, lock: Path) -> None:
    """Install the pinned closure exactly; --no-deps so nothing outside the lock sneaks in."""
    result = proc.run(
        [python, "-m", "pip", "install", "--no-deps", "--quiet", "-r", lock.resolve()], timeout=PIP_TIMEOUT
    )
    if not result.ok:
        raise WorkspaceError(f"installing {lock.name} failed. Last pip output:\n{result.tail()}")


def install_package(python: Path, repo: Path, pip_args: list[str]) -> None:
    """Install the challenge package from `repo` (normally editable)."""
    result = proc.run(
        [python, "-m", "pip", "install", "--no-deps", "--no-build-isolation", "--quiet", *pip_args],
        cwd=repo,
        timeout=PIP_TIMEOUT,
    )
    if not result.ok:
        raise WorkspaceError(f"installing the package from {repo} failed. Last pip output:\n{result.tail()}")


def build_env(venv: Path, python_version: str, lock: Path, repo: Path, pip_args: list[str]) -> Path:
    """Create `venv`, install the lock, then the package from `repo`. Returns the venv's python."""
    python = create_venv(venv, python_version)
    install_lock(python, lock)
    install_package(python, repo, pip_args)
    return python
