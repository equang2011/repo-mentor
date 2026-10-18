# RepoMentor Debug Gym

A local CLI for practicing repository-based debugging interviews. Each challenge is an
unfamiliar open-source Python repo, checked out at the commit just before a real upstream
bug fix, plus a customer-style ticket. You reproduce, diagnose, and fix the bug, and
hidden regression tests grade your fix.

## Install

Requires Python 3.10+ and git on PATH.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
repomentor --help        # or: python -m repomentor --help
```

Install in editable mode (`-e`). The demo challenge is read from this checkout's `demo/`
directory.

## Commands

```bash
repomentor list                  # challenges, difficulty, time budget, your status
repomentor start <challenge-id>  # fresh workspace; prints its path and a session id
repomentor grade <session-id>    # hidden checks against your copy; prints a report
repomentor reveal <session-id>   # after you're done: the answer key and the real fix
repomentor validate <id>         # authoring only: prove a challenge is sound
```

Data locations:

| What | Default | Override |
|---|---|---|
| Practice pack, sessions, repo cache | `~/.repomentor/` | `REPOMENTOR_HOME` |
| Workspaces | `~/repomentor-workspaces/` | `REPOMENTOR_WORKSPACES` |
| Demo challenges | `<this checkout>/demo/` | `REPOMENTOR_DEMO_DIR` |

## Isolation (read this)

Workspaces and grading use separate directories and separate virtualenvs. That is a
**spoiler boundary, not a security sandbox**: challenge code runs as you, with your
permissions. Only use vetted public repositories.

## How grading works

`grade` copies your `repo/` (without `.git`, venvs, and caches) to a temp directory and
puts back the original test files, so edits to existing tests don't count and new test
files are ignored. It then adds the hidden tests, builds a fresh venv from the lock, and
installs the package from that copy. Before running anything, it checks through pytest
that the package is imported from the copy. The report lists acceptance criteria as
PASS/FAIL, any existing tests that now fail, your diff stats, and whether you filled in
`diagnosis.md`. Exit codes: 0 PASS, 1 FAIL, 3 grader error (not your fault).

All challenge processes run in Python UTF-8 mode (`PYTHONUTF8=1`) with `PYTHONPATH`
cleared. Set `PYTHONUTF8=1` in your workspace shell too (the workspace README shows how).

## Practice protocol

1. Timebox to the challenge's budget (shown by `list`).
2. Read `ticket.md` and reproduce the bug before reading code.
3. Write a failing test first.
4. Use a deliberately limited assistant (plain chat, pasted snippets, a smaller model),
   not an agent with full repo access, to match the interview.
5. Talk through your reasoning out loud.
6. Fill in `diagnosis.md`.
7. `repomentor grade <session-id>`.
8. `repomentor reveal <session-id>` and compare your fix with the real one.

## Development

```bash
pytest              # fast tests
pytest -m slow      # full demo lifecycle (creates venvs; needs network on first run)
```
