"""Session metadata under $REPOMENTOR_HOME/sessions/<session-id>/."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from repomentor import paths
from repomentor.errors import SessionError
from repomentor.models import Session


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def new_session_id(challenge_id: str, when: datetime) -> str:
    return f"{challenge_id}-{when:%Y%m%d-%H%M%S}"


def session_dir(session_id: str) -> Path:
    return paths.sessions_dir() / session_id


def save(session: Session) -> None:
    d = session_dir(session.id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "session.json").write_text(json.dumps(session.to_dict(), indent=2) + "\n", encoding="utf-8")


def load(session_id: str) -> Session:
    path = session_dir(session_id) / "session.json"
    if not path.is_file():
        known = ", ".join(s.id for s in all_sessions()[-5:]) or "none yet"
        raise SessionError(
            f"unknown session '{session_id}'. `repomentor start` prints the session id "
            f"(recent sessions: {known})."
        )
    try:
        return Session.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError) as exc:
        raise SessionError(f"session metadata at {path} is unreadable: {exc}") from None


def all_sessions() -> list[Session]:
    root = paths.sessions_dir()
    if not root.is_dir():
        return []
    found = []
    for d in sorted(root.iterdir()):
        try:
            found.append(load_quiet(d / "session.json"))
        except (OSError, ValueError, TypeError):
            continue
    return found


def load_quiet(path: Path) -> Session:
    return Session.from_dict(json.loads(path.read_text(encoding="utf-8")))


def status_for(challenge_id: str) -> str:
    """not started | attempted | passed."""
    mine = [s for s in all_sessions() if s.challenge_id == challenge_id]
    if any(s.status == "passed" for s in mine):
        return "passed"
    return "attempted" if mine else "not started"
