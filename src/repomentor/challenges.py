"""Locating and loading challenges from the demo directory and the private pack."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from repomentor import paths
from repomentor.errors import ChallengeError, ManifestError
from repomentor.models import Manifest


@dataclass
class Challenge:
    manifest: Manifest
    directory: Path

    @property
    def id(self) -> str:
        return self.manifest.id

    @property
    def ticket_path(self) -> Path:
        return self.directory / "ticket.md"

    @property
    def lock_path(self) -> Path:
        return self.directory / self.manifest.install.lock_file

    @property
    def private_test_path(self) -> Path:
        return self.directory / self.manifest.private_tests.file

    @property
    def solution_notes_path(self) -> Path:
        return self.directory / "private" / "solution_notes.md"

    @property
    def manifest_path(self) -> Path:
        return self.directory / "manifest.json"


def load_manifest(path: Path) -> Manifest:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ManifestError(f"{path}: manifest.json not found") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path}: invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}") from None
    try:
        return Manifest.from_dict(data)
    except ManifestError as exc:
        raise ManifestError(f"{path}: {exc}") from None


def save_manifest(challenge: Challenge) -> None:
    text = json.dumps(challenge.manifest.to_dict(), indent=2) + "\n"
    challenge.manifest_path.write_text(text, encoding="utf-8")


def load_challenge(directory: Path) -> Challenge:
    manifest = load_manifest(directory / "manifest.json")
    if manifest.id != directory.name:
        raise ManifestError(f"{directory}: manifest id '{manifest.id}' does not match directory name")
    return Challenge(manifest=manifest, directory=directory)


def _roots() -> list[Path]:
    return [paths.demo_dir(), paths.pack_dir()]


def _candidate_dirs() -> list[Path]:
    dirs = []
    for root in _roots():
        if root.is_dir():
            dirs.extend(sorted(p for p in root.iterdir() if (p / "manifest.json").is_file()))
    return dirs


def find_challenge(challenge_id: str) -> Challenge:
    for directory in _candidate_dirs():
        if directory.name == challenge_id:
            return load_challenge(directory)
    raise ChallengeError(
        f"unknown challenge '{challenge_id}'. Run `repomentor list` to see available challenges."
    )


def all_challenges() -> tuple[list[Challenge], list[str]]:
    """Every loadable challenge, plus one error line per directory that failed to load."""
    found: list[Challenge] = []
    errors: list[str] = []
    for directory in _candidate_dirs():
        try:
            found.append(load_challenge(directory))
        except ManifestError as exc:
            # Only the directory name: error text could quote private fields.
            errors.append(f"{directory.name}: manifest failed to load ({type(exc).__name__})")
    return found, errors
