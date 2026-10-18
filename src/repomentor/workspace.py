"""`start`: create a fresh workspace for a challenge."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from repomentor import envs, gitops, paths, proc, sessions, trees
from repomentor.challenges import Challenge, find_challenge
from repomentor.errors import ChallengeError, RepoMentorError, WorkspaceError
from repomentor.models import Session

# Set by the workspace venv's activation scripts, matching what the grader uses.
WORKSPACE_ENV = {"PYTHONUTF8": "1"}

DIAGNOSIS_TEMPLATE = """\
# Diagnosis

## Root-cause hypothesis


## Supporting evidence


## What I changed


## How I verified it

"""


def _activate_hint() -> str:
    if os.name == "nt":
        return ".venv\\Scripts\\Activate.ps1      # PowerShell (cmd: .venv\\Scripts\\activate.bat)"
    return "source .venv/bin/activate"


def workspace_readme(challenge: Challenge) -> str:
    m = challenge.manifest
    test_cmd = "python -m pytest " + " ".join(m.existing_tests.pytest_args)
    return f"""\
# Workspace for {m.id}

- `ticket.md` is the bug report. Start there.
- `repo/` is the repository. It has one git commit ("Initial snapshot"), so
  `git diff` shows exactly what you changed.
- `diagnosis.md` is optional: record your root-cause hypothesis, evidence, change, and verification.
- `.venv/` has the pinned dependencies and the package installed in editable mode.

## Setup

```
{_activate_hint()}
cd repo
{test_cmd}
```

Activating the venv also sets `PYTHONUTF8=1`, which runs Python in UTF-8 mode like
the grader does. `deactivate` does not unset it; open a new shell if you need to.

Time budget: {m.time_budget_minutes} minutes. When you're done, run `repomentor grade <session-id>`.
The grader restores the original test files and ignores new test files, so write any
tests you like.
"""


def _check_startable(challenge: Challenge, allow_unvalidated: bool) -> None:
    if not allow_unvalidated and not challenge.manifest.is_validated:
        raise ChallengeError(
            f"challenge '{challenge.id}' has not passed validation, so it can't be started. "
            f"An author must run `repomentor validate {challenge.id}` first."
        )


def start(
    challenge_id: str,
    *,
    allow_unvalidated: bool = False,
    when: datetime | None = None,
) -> Session:
    challenge = find_challenge(challenge_id)
    _check_startable(challenge, allow_unvalidated)
    m = challenge.manifest
    proc.require_tool("git")
    envs.find_python(m.python_version)  # fail early, before any work

    when = when or sessions.now_utc()
    session_id = sessions.new_session_id(m.id, when)
    ws = paths.workspaces_dir() / session_id
    if ws.exists():
        raise WorkspaceError(
            f"workspace already exists at {ws}. Remove it, or wait a second and start again for a new session id."
        )

    bare = gitops.ensure_repo(m.repo.url, [m.buggy_sha, m.fixed_sha])
    try:
        _build_workspace(challenge, bare, ws)
    except BaseException:
        trees.rmtree(ws)  # don't leave a half-built workspace that blocks a retry
        raise

    session = Session(id=session_id, challenge_id=m.id, started_at=when.isoformat(), workspace=str(ws.resolve()))
    sessions.save(session)
    return session


def _build_workspace(challenge: Challenge, bare: Path, ws: Path) -> None:
    m = challenge.manifest
    ws.mkdir(parents=True)
    repo = ws / "repo"
    trees.export_buggy(challenge, bare, repo)
    gitops.init_snapshot(repo)
    shutil.copy2(challenge.ticket_path, ws / "ticket.md")
    (ws / "diagnosis.md").write_text(DIAGNOSIS_TEMPLATE, encoding="utf-8")
    (ws / "README.md").write_text(workspace_readme(challenge), encoding="utf-8")
    try:
        envs.build_env(ws / ".venv", m.python_version, challenge.lock_path, repo, m.install.pip_args)
    except RepoMentorError as exc:
        raise WorkspaceError(f"setting up the workspace venv failed: {exc}") from None
    envs.add_activation_env(ws / ".venv", WORKSPACE_ENV)
