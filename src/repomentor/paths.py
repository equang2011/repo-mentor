"""Filesystem locations. All of them can be redirected with environment variables."""

from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    """$REPOMENTOR_HOME, default ~/.repomentor."""
    value = os.environ.get("REPOMENTOR_HOME")
    return Path(value).expanduser() if value else Path.home() / ".repomentor"


def pack_dir() -> Path:
    return home() / "pack"


def sessions_dir() -> Path:
    """$REPOMENTOR_SESSIONS, default $REPOMENTOR_HOME/sessions (validate uses a throwaway one)."""
    value = os.environ.get("REPOMENTOR_SESSIONS")
    return Path(value).expanduser() if value else home() / "sessions"


def repo_cache_dir() -> Path:
    """Bare clones of upstream repositories, shared by all challenges."""
    return home() / "repos"


def workspaces_dir() -> Path:
    """$REPOMENTOR_WORKSPACES, default ~/repomentor-workspaces."""
    value = os.environ.get("REPOMENTOR_WORKSPACES")
    return Path(value).expanduser() if value else Path.home() / "repomentor-workspaces"


def demo_dir() -> Path:
    """$REPOMENTOR_DEMO_DIR, default the `demo/` directory of this checkout.

    The default assumes an editable install (src layout: src/repomentor/paths.py).
    """
    value = os.environ.get("REPOMENTOR_DEMO_DIR")
    if value:
        return Path(value).expanduser()
    return Path(__file__).resolve().parents[2] / "demo"
