"""Synthetic manifest data for harness tests. Never references the practice pack."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

SHA_A = "a" * 40
SHA_B = "b" * 40

BASE: dict[str, Any] = {
    "schema_version": 1,
    "id": "demo-001",
    "kind": "demo",
    "origin": "upstream-fix",
    "public_fields": ["id", "kind", "repo.name", "difficulty", "time_budget_minutes"],
    "repo": {
        "name": "examplelib",
        "url": "https://example.invalid/examplelib.git",
        "license": "MIT",
        "source_file_count": 25,
        "source_count_command": "find examplelib -name '*.py' | wc -l",
    },
    "package": {"import_name": "examplelib", "version": "1.0.0"},
    "buggy_sha": SHA_A,
    "fixed_sha": SHA_B,
    "python_version": "3.13",
    "install": {"lock_file": "lock.txt", "pip_args": ["-e", "."]},
    "existing_tests": {"pytest_args": ["tests"], "test_paths": ["tests"], "deselect": []},
    "private_tests": {"file": "private/test_regression.py", "dest": "tests/test_zz_private.py"},
    "acceptance_criteria": [
        {"id": "AC1", "text": "It works.", "tests": ["test_works"]},
    ],
    "difficulty": "easy",
    "time_budget_minutes": 30,
    "upstream": {"issue_url": "https://example.invalid/issues/1", "fix_url": None},
    "validation": None,
}


def manifest_dict(**overrides: Any) -> dict[str, Any]:
    data = copy.deepcopy(BASE)
    for key, value in overrides.items():
        data[key] = value
    return data


def write_challenge(root: Path, data: dict[str, Any] | None = None, **overrides: Any) -> Path:
    data = data or manifest_dict(**overrides)
    directory = root / data["id"]
    (directory / "private").mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    (directory / "ticket.md").write_text("# Ticket\n", encoding="utf-8")
    (directory / "lock.txt").write_text("", encoding="utf-8")
    (directory / "private" / "test_regression.py").write_text("def test_works():\n    assert True\n")
    return directory
