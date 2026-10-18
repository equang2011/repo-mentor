"""The workspace venv's activation scripts set PYTHONUTF8=1."""

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from repomentor import envs, workspace

PROBE = "import sys; print('utf8_mode=' + str(sys.flags.utf8_mode))"


@pytest.fixture
def venv(tmp_path):
    path = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(path)], check=True)
    return path


def _clean_env():
    return {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "VIRTUAL_ENV", "PYTHONPATH")}


def test_scripts_export_variable_and_keep_line_endings(venv):
    scripts = envs.venv_python(venv).parent
    before = {p.name: p.read_bytes() for p in scripts.iterdir() if p.name in envs._ACTIVATE_LINES}
    changed = envs.add_activation_env(venv, {"PYTHONUTF8": "1"})
    assert {p.name for p in changed} == set(before)
    for path in changed:
        data = path.read_bytes()
        assert data.startswith(before[path.name])  # appended, original untouched
        assert b"PYTHONUTF8" in data[len(before[path.name]):]
        if b"\r\n" not in before[path.name]:
            assert b"\r\n" not in data  # bash would choke on CRLF
    assert b'export PYTHONUTF8="1"' in (scripts / "activate").read_bytes()


def test_powershell_signature_block_is_dropped(venv):
    ps1 = envs.venv_python(venv).parent / "Activate.ps1"
    ps1.write_bytes(b"Write-Host hi\r\n# SIG # Begin signature block\r\n# MIIabc\r\n# SIG # End signature block\r\n")
    envs.add_activation_env(venv, {"PYTHONUTF8": "1"})
    data = ps1.read_bytes()
    assert b"SIG #" not in data and data.endswith(b'$env:PYTHONUTF8 = "1"\r\n')


def _bash() -> str | None:
    if os.name != "nt":
        return shutil.which("bash")
    # On Windows, `bash` on PATH is often WSL's launcher; use Git for Windows' bash.
    git = shutil.which("git")
    if git:
        for candidate in (Path(git).parents[1] / "bin" / "bash.exe", Path(git).parents[1] / "usr" / "bin" / "bash.exe"):
            if candidate.is_file():
                return str(candidate)
    return None


def _shell_commands(venv: Path):
    scripts = envs.venv_python(venv).parent
    bash = _bash()
    if bash:
        yield "bash", [bash, "-c", f'source "{(scripts / "activate").as_posix()}" && python -c "{PROBE}"']
    if os.name == "nt":
        ps = shutil.which("powershell") or shutil.which("pwsh")
        if ps:
            yield "powershell", [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                                 f"& {{ . '{scripts / 'Activate.ps1'}'; python -c \"{PROBE}\" }}"]
        # A raw string: cmd.exe doesn't understand list2cmdline's backslash-escaped quotes.
        yield "cmd", f'cmd /c call "{scripts / "activate.bat"}" && python -c "{PROBE}"'


def test_activation_enables_utf8_mode_in_real_shells(venv):
    envs.add_activation_env(venv, {"PYTHONUTF8": "1"})
    shells = list(_shell_commands(venv))
    if not shells:
        pytest.skip("no supported shell found")
    for name, cmd in shells:
        out = subprocess.run(cmd, env=_clean_env(), capture_output=True, text=True, timeout=60)
        assert "utf8_mode=1" in out.stdout, f"{name}: {out.stdout!r} {out.stderr!r}"


def test_start_sets_up_activation(challenge_dir, fake_envs):
    s = workspace.start("demo-001", when=datetime(2026, 1, 2, tzinfo=timezone.utc))
    activate = envs.venv_python(Path(s.workspace) / ".venv").parent / "activate"
    assert b"PYTHONUTF8" in activate.read_bytes()
    assert "Activating the venv also sets `PYTHONUTF8=1`" in (Path(s.workspace) / "README.md").read_text()
