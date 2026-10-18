"""Command-line entry point: `repomentor <command>` or `python -m repomentor <command>`."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from repomentor import __version__, challenges, grader, reveal, sessions, validate, workspace
from repomentor.errors import GraderError, RepoMentorError


def cmd_list(args: argparse.Namespace) -> int:
    found, broken = challenges.all_challenges()
    listed = [c for c in found if c.manifest.is_validated]
    hidden = len(found) - len(listed)
    if not listed:
        print("No validated challenges yet.")
    else:
        rows = [("ID", "REPO", "DIFFICULTY", "BUDGET", "STATUS")]
        for c in listed:
            view = c.manifest.public_view()
            rows.append((
                c.id, view.get("repo.name", "?"), view.get("difficulty", "?"),
                f"{view['time_budget_minutes']} min" if "time_budget_minutes" in view else "?",
                sessions.status_for(c.id),
            ))
        widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
        for r in rows:
            print("  ".join(cell.ljust(w) for cell, w in zip(r, widths)).rstrip())
    if hidden:
        print(f"\n({hidden} unvalidated challenge(s) hidden)")
    for line in broken:
        print(f"warning: {line}", file=sys.stderr)
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    challenges.find_challenge(args.challenge_id)  # fail fast on an unknown id
    print(f"Creating workspace for {args.challenge_id} (export, git snapshot, venv)...", flush=True)
    session = workspace.start(args.challenge_id)
    ws = session.workspace
    print(f"""
Session:   {session.id}
Workspace: {ws}
  ticket.md      the bug report (start here)
  repo/          the repository, one "Initial snapshot" commit
  diagnosis.md   optional notes template
  README.md      setup and test commands

When you're done: repomentor grade {session.id}""")
    return 0


def cmd_grade(args: argparse.Namespace) -> int:
    sessions.load(args.session_id)  # fail fast on an unknown id
    print(f"Grading {args.session_id} in a fresh copy (this builds a venv; it can take a minute)...", flush=True)
    try:
        report = grader.grade(args.session_id)
    except GraderError as exc:
        print(f"\nGRADER ERROR (a problem with the grader, not with your fix):\n{exc}", file=sys.stderr)
        return exc.exit_code
    challenge = challenges.find_challenge(report.challenge_id)
    print()
    print(grader.render_report(report, challenge.manifest.time_budget_minutes), end="")
    return 0 if report.verdict == "PASS" else 1


def cmd_reveal(args: argparse.Namespace) -> int:
    session = sessions.load(args.session_id)
    if not args.yes:
        if not sys.stdin.isatty():
            print("reveal needs confirmation: rerun in a terminal, or pass --yes.", file=sys.stderr)
            return 2
        try:
            answer = input(f"Show the answer key for {session.challenge_id}? It can't be unseen. Type 'yes': ")
        except EOFError:  # e.g. stdin is NUL on Windows, which reports itself as a TTY
            answer = ""
        if answer.strip().lower() != "yes":
            print("Not revealed.")
            return 0
    print(reveal.reveal_text(args.session_id))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    validate.validate(args.challenge_id)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repomentor", description="RepoMentor Debug Gym")
    parser.add_argument("--version", action="version", version=f"repomentor {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="list challenges (no spoilers)")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("start", help="create a fresh workspace for a challenge")
    p.add_argument("challenge_id")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("grade", help="run hidden checks against a session's workspace")
    p.add_argument("session_id")
    p.set_defaults(func=cmd_grade)

    p = sub.add_parser("reveal", help="show the answer key for a session's challenge")
    p.add_argument("session_id")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.set_defaults(func=cmd_reveal)

    p = sub.add_parser("validate", help="(authoring) validate a challenge end to end")
    p.add_argument("challenge_id")
    p.set_defaults(func=cmd_validate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")  # Windows consoles can't print every character
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RepoMentorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
