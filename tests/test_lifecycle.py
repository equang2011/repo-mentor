"""start / grade / reveal / validate against the synthetic upstream, with fake installers."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import synthetic
from repomentor import cli, grader, leaks, reveal, sessions, validate, workspace
from repomentor.challenges import find_challenge
from repomentor.errors import ChallengeError, GraderError, ValidationError, WorkspaceError

WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def fix_workspace(session) -> Path:
    src = Path(session.workspace) / "repo" / "src" / "minicalc" / "__init__.py"
    src.write_text(synthetic.FIXED_SRC)
    return src


def test_start_creates_clean_workspace(challenge_dir, fake_envs):
    s = workspace.start("demo-001", when=WHEN)
    ws = Path(s.workspace)
    assert s.id == "demo-001-20260102-030405"
    assert {p.name for p in ws.iterdir()} >= {"repo", "ticket.md", "diagnosis.md", "README.md", ".venv"}
    assert (ws / "repo" / "src" / "minicalc" / "__init__.py").read_text() == synthetic.BUGGY_SRC
    assert not list(ws.rglob("test_regression.py")) and not list(ws.rglob("solution_notes.md"))
    assert sessions.load(s.id).challenge_id == "demo-001"
    assert leaks.check_workspace(ws, find_challenge("demo-001")) == []


def test_start_refuses_existing_workspace(challenge_dir, fake_envs, isolated_home, tmp_path):
    (tmp_path / "workspaces" / "demo-001-20260102-030405").mkdir()
    with pytest.raises(WorkspaceError, match="workspace already exists"):
        workspace.start("demo-001", when=WHEN)


def test_start_refuses_unvalidated(tmp_path, upstream, fake_envs):
    synthetic.write_challenge(tmp_path / "demo", synthetic.challenge_manifest(*upstream, validation=None))
    with pytest.raises(ChallengeError, match="has not passed validation.*repomentor validate demo-001"):
        workspace.start("demo-001", when=WHEN)


def test_start_unknown_challenge(fake_envs):
    with pytest.raises(ChallengeError, match="unknown challenge 'p99'"):
        workspace.start("p99")


def test_start_cleans_up_after_install_failure(challenge_dir, fake_envs, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise WorkspaceError("installing lock.txt failed. Last pip output:\nERROR: no such package")

    monkeypatch.setattr("repomentor.envs.install_lock", boom)
    with pytest.raises(WorkspaceError, match="no such package"):
        workspace.start("demo-001", when=WHEN)
    assert not (tmp_path / "workspaces" / "demo-001-20260102-030405").exists()


def test_grade_untouched_fails_and_fix_passes(challenge_dir, fake_envs):
    s = workspace.start("demo-001", when=WHEN)
    report = grader.grade(s.id)
    assert report.verdict == "FAIL"
    assert [(c.id, c.passed) for c in report.criteria] == [("AC1", False), ("AC2", True)]
    assert report.newly_failing == [] and report.existing_passed == 2
    assert report.diagnosis == "template only (not filled in)"

    fix_workspace(s)
    report = grader.grade(s.id)
    assert report.verdict == "PASS"
    assert report.diff.files_changed == 1 and report.diff.lines_added == 1 and report.diff.lines_removed == 1
    assert sessions.load(s.id).status == "passed"
    saved = list((sessions.session_dir(s.id) / "grades").glob("grade-*.json"))
    assert saved and json.loads(saved[-1].read_text())["verdict"] == "PASS"


def test_install_env_reaches_workspace_and_grading_installs(tmp_path, upstream, fake_envs):
    data = synthetic.challenge_manifest(*upstream)
    data["install"]["env"] = {"PRETEND_VERSION": "9.9.9"}
    synthetic.write_challenge(tmp_path / "demo", data)
    s = workspace.start("demo-001", when=WHEN)
    grader.grade(s.id)
    assert fake_envs.install_envs == [{"PRETEND_VERSION": "9.9.9"}] * 2


def test_grade_restores_tests_and_ignores_new_ones(challenge_dir, fake_envs):
    s = workspace.start("demo-001", when=WHEN)
    fix_workspace(s)
    tests = Path(s.workspace) / "repo" / "tests"
    (tests / "test_basic.py").write_text("def test_in_range():\n    assert False\n")  # sabotage
    (tests / "test_mine.py").write_text("def test_new():\n    assert False\n")
    report = grader.grade(s.id)
    assert report.verdict == "PASS"
    assert report.diff.tests_modified
    assert any("modified existing test files" in n for n in report.notes)


def test_grade_reports_newly_failing_existing_tests(challenge_dir, fake_envs):
    s = workspace.start("demo-001", when=WHEN)
    src = fix_workspace(s)
    # Fixes AC1 but breaks values below the range.
    src.write_text(synthetic.FIXED_SRC.replace("        return low\n    if value > high", "        return value\n    if value > high"))
    report = grader.grade(s.id)
    assert report.verdict == "FAIL"
    assert report.newly_failing == ["tests/test_basic.py::test_below"]
    assert [(c.id, c.passed) for c in report.criteria] == [("AC1", True), ("AC2", False)]


def test_grade_detects_stale_code(challenge_dir, fake_envs, tmp_path):
    s = workspace.start("demo-001", when=WHEN)
    fix_workspace(s)
    fake_envs.package_override = Path(s.workspace) / "repo"  # the workspace, not the grading copy
    with pytest.raises(GraderError, match="Refusing to grade against stale code"):
        grader.grade(s.id)


def test_report_never_names_private_tests(challenge_dir, fake_envs):
    s = workspace.start("demo-001", when=WHEN)
    text = grader.render_report(grader.grade(s.id))
    assert "test_above_range" not in text and "test_zz_private" not in text and "assert" not in text


def test_grade_cli_exit_codes(challenge_dir, fake_envs, capsys):
    s = workspace.start("demo-001", when=WHEN)
    assert cli.main(["grade", s.id]) == 1
    fix_workspace(s)
    assert cli.main(["grade", s.id]) == 0
    assert "VERDICT: PASS" in capsys.readouterr().out
    assert cli.main(["grade", "nope"]) == 2


def test_grader_error_is_distinguished(challenge_dir, fake_envs, monkeypatch, capsys):
    s = workspace.start("demo-001", when=WHEN)

    def broken(*a, **k):
        raise WorkspaceError("pip exploded")

    monkeypatch.setattr("repomentor.envs.install_lock", broken)
    assert cli.main(["grade", s.id]) == 3
    assert "GRADER ERROR (a problem with the grader, not with your fix)" in capsys.readouterr().err


def test_leak_check_finds_history_private_files_and_issue_refs(challenge_dir, fake_envs):
    s = workspace.start("demo-001", when=WHEN)
    ws = Path(s.workspace)
    challenge = find_challenge("demo-001")
    (ws / "repo" / "NOTES.md").write_text("see #77 upstream\n")
    (ws / "copy.py").write_bytes(challenge.private_test_path.read_bytes())
    from repomentor import gitops
    gitops.git("-c", "user.name=x", "-c", "user.email=x@x", "commit", "-q", "--allow-empty", "-m", "2", cwd=ws / "repo")
    problems = "\n".join(leaks.check_workspace(ws, challenge))
    assert "2 commits" in problems
    assert "identical to private file test_regression.py" in problems
    assert "NOTES.md: contains upstream reference '#77'" in problems


def test_reveal_shows_fix(challenge_dir, fake_envs):
    s = workspace.start("demo-001", when=WHEN)
    text = reveal.reveal_text(s.id)
    assert "clamp returned low instead of high" in text
    assert "-        return low" in text and "+        return high" in text
    assert "issues/77" in text


def test_reveal_requires_confirmation(challenge_dir, fake_envs, monkeypatch, capsys):
    s = workspace.start("demo-001", when=WHEN)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    assert cli.main(["reveal", s.id]) == 0
    assert "Not revealed." in capsys.readouterr().out


def test_list_shows_only_whitelisted_fields(tmp_path, upstream, isolated_home, capsys):
    m = synthetic.challenge_manifest(*upstream, id="p01", kind="practice")
    synthetic.write_challenge(isolated_home / "pack", m)
    synthetic.write_challenge(isolated_home / "pack", synthetic.challenge_manifest(*upstream, id="p02",
                                                                                  kind="practice", validation=None))
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "p01" in out and "minicalc" in out and "not started" in out
    assert "p02" not in out and "1 unvalidated challenge(s) hidden" in out
    for secret in (m["buggy_sha"], m["fixed_sha"][:10], "issues/77", "test_above_range", "Values above"):
        assert secret not in out


def test_validate_passes_and_records(tmp_path, upstream, fake_envs):
    d = synthetic.write_challenge(tmp_path / "demo", synthetic.challenge_manifest(*upstream, validation=None))
    checks = validate.validate("demo-001", log=lambda _: None)
    assert [c.step for c in checks] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert json.loads((d / "manifest.json").read_text())["validation"]["status"] == "passed"


def test_synthetic_challenge_validates_starts_and_reveals(tmp_path, upstream, fake_envs):
    d = synthetic.write_synthetic_challenge(tmp_path / "demo", *upstream)
    checks = validate.validate("demo-001", log=lambda _: None)
    assert [c.step for c in checks] == [1, 2, 3, 4, 5, 6, 7, 8]

    s = workspace.start("demo-001", when=WHEN)
    src = Path(s.workspace) / "repo" / "src" / "minicalc" / "__init__.py"
    assert src.read_text() == synthetic.BUGGY_SRC  # injection applied
    assert not list(Path(s.workspace).rglob("injection.patch"))

    text = reveal.reveal_text(s.id)
    assert "-        return low" in text and "+        return high" in text  # reversed injection
    assert json.loads((d / "manifest.json").read_text())["validation"]["status"] == "passed"


def test_synthetic_challenge_requires_matching_shas(tmp_path, upstream, fake_envs):
    url, buggy, fixed = upstream
    d = synthetic.write_synthetic_challenge(tmp_path / "demo", url, buggy, fixed)
    data = json.loads((d / "manifest.json").read_text())
    data["buggy_sha"] = buggy
    (d / "manifest.json").write_text(json.dumps(data))
    with pytest.raises(ValidationError, match="step 1 .*clean commit as both"):
        validate.validate("demo-001", log=lambda _: None)


def test_validate_rejects_private_test_that_passes_at_buggy_ref(tmp_path, upstream, fake_envs):
    weak = synthetic.PRIVATE_TESTS.replace("assert clamp(11, 0, 10) == 10\n    assert clamp(99, -5, 7) == 7",
                                           "assert clamp(5, 0, 10) == 5")
    d = synthetic.write_challenge(tmp_path / "demo", synthetic.challenge_manifest(*upstream, validation=None), weak)
    with pytest.raises(ValidationError, match=r"step 5 .*test_above_range \(AC1\) passed at the buggy ref"):
        validate.validate("demo-001", log=lambda _: None)
    assert json.loads((d / "manifest.json").read_text())["validation"]["status"] == "failed"


def test_validate_rejects_import_error_as_failure(tmp_path, upstream, fake_envs):
    broken = "from minicalc import clamp_v2\n\n" + synthetic.PRIVATE_TESTS
    synthetic.write_challenge(tmp_path / "demo", synthetic.challenge_manifest(*upstream, validation=None), broken)
    with pytest.raises(ValidationError, match="step 5 .*collection errors"):
        validate.validate("demo-001", log=lambda _: None)


def test_validate_rejects_non_parent_buggy_ref(tmp_path, upstream, fake_envs):
    url, buggy, fixed = upstream
    synthetic.write_challenge(tmp_path / "demo", synthetic.challenge_manifest(url, fixed, buggy, validation=None))
    with pytest.raises(ValidationError, match="step 1 .*must be a parent of fixed_sha"):
        validate.validate("demo-001", log=lambda _: None)
