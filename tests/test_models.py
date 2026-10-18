import json

import pytest

from repomentor import challenges
from repomentor.errors import ChallengeError, ManifestError
from repomentor.models import Manifest

from factories import manifest_dict, write_challenge


def test_valid_manifest_parses():
    m = Manifest.from_dict(manifest_dict())
    assert m.id == "demo-001"
    assert m.repo.license == "MIT"
    assert m.acceptance_criteria[0].tests == ["test_works"]
    assert m.existing_tests.timeout_seconds == 600
    assert not m.is_validated


def test_round_trip():
    m = Manifest.from_dict(manifest_dict())
    assert Manifest.from_dict(m.to_dict()) == m


def test_install_env_defaults_empty_and_round_trips():
    assert Manifest.from_dict(manifest_dict()).install.env == {}
    install = {"lock_file": "lock.txt", "pip_args": ["-e", "."], "env": {"PRETEND_VERSION": "1.2.3"}}
    m = Manifest.from_dict(manifest_dict(install=install))
    assert m.install.env == {"PRETEND_VERSION": "1.2.3"}
    assert Manifest.from_dict(m.to_dict()) == m


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"kind": "tutorial"}, "'kind' must be one of"),
        ({"buggy_sha": "abc123"}, "full 40-character"),
        ({"difficulty": "extreme"}, "'difficulty' must be one of"),
        ({"time_budget_minutes": 0}, "positive integer"),
        ({"acceptance_criteria": []}, "at least one criterion"),
        ({"acceptance_criteria": [{"id": "AC1", "text": "x", "tests": []}]}, "maps to no private tests"),
        ({"acceptance_criteria": [{"id": "1", "text": "x", "tests": ["t"]}]}, "must look like AC1"),
        ({"public_fields": ["id", "upstream.issue_url"]}, "non-whitelisted"),
        ({"schema_version": 99}, "unsupported schema_version"),
        ({"origin": "synthetic"}, "injection_patch"),
        ({"kind": "practice", "id": "sqlparse-bug-1"}, "must be opaque"),
        ({"install": {"lock_file": "lock.txt", "pip_args": [], "env": {"X": 1}}}, "mapping names to strings"),
        ({"install": {"lock_file": "lock.txt", "pip_args": [], "env": ["X=1"]}}, "mapping names to strings"),
    ],
)
def test_invalid_manifest_rejected(overrides, message):
    with pytest.raises(ManifestError, match=message):
        Manifest.from_dict(manifest_dict(**overrides))


def test_missing_nested_field_names_path():
    data = manifest_dict()
    del data["repo"]["license"]
    with pytest.raises(ManifestError, match=r"'repo\.license'"):
        Manifest.from_dict(data)


def test_duplicate_criterion_ids_rejected():
    ac = {"id": "AC1", "text": "x", "tests": ["t"]}
    with pytest.raises(ManifestError, match="duplicate"):
        Manifest.from_dict(manifest_dict(acceptance_criteria=[ac, ac]))


def test_public_view_only_whitelisted_fields():
    m = Manifest.from_dict(manifest_dict(kind="practice", id="p01"))
    view = m.public_view()
    assert set(view) == {"id", "kind", "repo.name", "difficulty", "time_budget_minutes"}
    rendered = json.dumps(view)
    assert "issues" not in rendered and m.buggy_sha not in rendered


def test_find_challenge_in_demo_dir(tmp_path, monkeypatch):
    write_challenge(tmp_path / "demo")
    assert challenges.find_challenge("demo-001").manifest.repo.name == "examplelib"


def test_find_challenge_in_pack(isolated_home):
    write_challenge(isolated_home / "pack", manifest_dict(kind="practice", id="p07"))
    assert challenges.find_challenge("p07").manifest.kind == "practice"


def test_unknown_challenge():
    with pytest.raises(ChallengeError, match="unknown challenge 'nope'.*repomentor list"):
        challenges.find_challenge("nope")


def test_bad_json_manifest(tmp_path):
    d = tmp_path / "demo" / "demo-001"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError, match="invalid JSON at line 1"):
        challenges.find_challenge("demo-001")


def test_manifest_id_must_match_directory(tmp_path):
    d = write_challenge(tmp_path / "demo")
    d.rename(d.parent / "demo-002")
    with pytest.raises(ManifestError, match="does not match directory"):
        challenges.find_challenge("demo-002")


def test_all_challenges_reports_broken_without_details(isolated_home):
    write_challenge(isolated_home / "pack", manifest_dict(kind="practice", id="p01"))
    broken = isolated_home / "pack" / "p02"
    broken.mkdir()
    (broken / "manifest.json").write_text('{"secret_root_cause": "parser"}', encoding="utf-8")
    found, errors = challenges.all_challenges()
    assert [c.id for c in found] == ["p01"]
    assert errors == ["p02: manifest failed to load (ManifestError)"]
