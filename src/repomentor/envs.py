"""Finding the right Python and building per-challenge virtualenvs from the lock file."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Mapping

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


def install_package(python: Path, repo: Path, pip_args: list[str], env: Mapping[str, str] | None = None) -> None:
    """Install the challenge package from `repo` (normally editable), with optional extra `env`."""
    result = proc.run(
        [python, "-m", "pip", "install", "--no-deps", "--no-build-isolation", "--quiet", *pip_args],
        cwd=repo,
        timeout=PIP_TIMEOUT,
        env=env,
    )
    if not result.ok:
        raise WorkspaceError(f"installing the package from {repo} failed. Last pip output:\n{result.tail()}")


_SIGNATURE_MARKER = b"# SIG # Begin signature block"

# Activation script name -> (comment prefix, line template). Missing scripts are skipped.
_ACTIVATE_LINES = {
    "activate": ("#", 'export {name}="{value}"'),
    "activate.bat": ("rem", 'set "{name}={value}"'),
    "Activate.ps1": ("#", '$env:{name} = "{value}"'),
    "activate.fish": ("#", 'set -gx {name} "{value}"'),
    "activate.csh": ("#", 'setenv {name} "{value}"'),
}


def add_activation_env(venv: Path, variables: dict[str, str]) -> list[Path]:
    """Make the venv's activation scripts export `variables`. Returns the scripts changed.

    Edits bytes so each script keeps its own line endings (bash breaks on CRLF). A
    PowerShell signature block, if present, is dropped: the edit would invalidate it.
    """
    scripts_dir = venv_python(venv).parent
    changed = []
    for name, (comment, template) in _ACTIVATE_LINES.items():
        script = scripts_dir / name
        if not script.is_file():
            continue
        data = script.read_bytes()
        nl = b"\r\n" if b"\r\n" in data else b"\n"
        if _SIGNATURE_MARKER in data:
            data = data[: data.index(_SIGNATURE_MARKER)]
        lines = [f"{comment} Added by RepoMentor: match the grader's environment.".encode()]
        lines += [template.format(name=k, value=v).encode() for k, v in variables.items()]
        if not data.endswith(nl):
            data += nl
        script.write_bytes(data + nl.join(lines) + nl)
        changed.append(script)
    return changed


def build_env(
    venv: Path, python_version: str, lock: Path, repo: Path, pip_args: list[str], env: Mapping[str, str] | None = None
) -> Path:
    """Create `venv`, install the lock, then the package from `repo`. Returns the venv's python."""
    python = create_venv(venv, python_version)
    install_lock(python, lock)
    install_package(python, repo, pip_args, env)
    return python
