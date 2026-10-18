"""Command-line entry point: `repomentor <command>` or `python -m repomentor <command>`."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from repomentor import __version__
from repomentor.errors import RepoMentorError


def _not_implemented(args: argparse.Namespace) -> int:
    raise RepoMentorError(f"`{args.command}` is not implemented yet")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repomentor", description="RepoMentor Debug Gym")
    parser.add_argument("--version", action="version", version=f"repomentor {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="list challenges (no spoilers)")
    p.set_defaults(func=_not_implemented)

    p = sub.add_parser("start", help="create a fresh workspace for a challenge")
    p.add_argument("challenge_id")
    p.set_defaults(func=_not_implemented)

    p = sub.add_parser("grade", help="run hidden checks against a session's workspace")
    p.add_argument("session_id")
    p.set_defaults(func=_not_implemented)

    p = sub.add_parser("reveal", help="show the answer key for a session's challenge")
    p.add_argument("session_id")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.set_defaults(func=_not_implemented)

    p = sub.add_parser("validate", help="(authoring) validate a challenge end to end")
    p.add_argument("challenge_id")
    p.set_defaults(func=_not_implemented)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RepoMentorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
