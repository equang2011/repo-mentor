"""Running external commands: argument lists, timeouts, and a controlled environment."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from repomentor.errors import ToolError

# Variables that would let the caller's environment leak code or config into a
# challenge venv (for example a PYTHONPATH pointing at another checkout).
_SCRUBBED = ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "VIRTUAL_ENV", "PYTHONSAFEPATH", "PIP_REQUIRE_VIRTUALENV")

# UTF-8 mode removes Windows locale differences (cp1252 file reads) and a fixed
# hash seed makes set/dict-order-dependent output reproducible.
_FORCED = {
    "PYTHONUTF8": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    "PIP_NO_INPUT": "1",
}


@dataclass
class Result:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def tail(self, lines: int = 25) -> str:
        text = (self.stdout + "\n" + self.stderr).strip()
        return "\n".join(text.splitlines()[-lines:])


def child_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _SCRUBBED}
    env.update(_FORCED)
    if extra:
        env.update(extra)
    return env


def run(
    args: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    timeout: float = 300,
    env: Mapping[str, str] | None = None,
    check: bool = False,
    what: str | None = None,
) -> Result:
    """Run a command. A missing executable raises ToolError; a timeout returns timed_out=True.

    With check=True a non-zero exit (or timeout) raises ToolError naming `what`.
    """
    argv = [str(a) for a in args]
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=child_env(env),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        result = Result(argv, proc.returncode, proc.stdout, proc.stderr)
    except FileNotFoundError:
        raise ToolError(f"'{argv[0]}' was not found. Is it installed and on PATH?") from None
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        result = Result(argv, -1, out, err, timed_out=True)
    if check and not result.ok:
        label = what or " ".join(argv[:3])
        reason = f"timed out after {timeout:.0f}s" if result.timed_out else f"exited with {result.returncode}"
        raise ToolError(f"{label} {reason}:\n{result.tail()}")
    return result


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise ToolError(f"'{name}' is required but was not found on PATH. Install it and retry.")
    return path
