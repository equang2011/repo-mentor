"""Full demo-001 lifecycle with real venvs and pip. Slow; needs network on first run."""

import tempfile
from pathlib import Path

import pytest

from repomentor import gitops, grader, paths, reveal, trees, workspace
from repomentor.challenges import find_challenge

REAL_DEMO = Path(__file__).resolve().parents[1] / "demo"


@pytest.mark.slow
def test_demo_lifecycle(monkeypatch):
    monkeypatch.setenv("REPOMENTOR_DEMO_DIR", str(REAL_DEMO))
    challenge = find_challenge("demo-001")
    assert challenge.manifest.is_validated, "run `repomentor validate demo-001` first"

    session = workspace.start("demo-001")
    repo = Path(session.workspace) / "repo"
    assert gitops.commit_count(repo) == 1

    untouched = grader.grade(session.id)
    assert untouched.verdict == "FAIL"
    assert [c.passed for c in untouched.criteria] == [False, False, True]

    m = challenge.manifest
    bare = gitops.ensure_repo(m.repo.url, [m.fixed_sha])
    with tempfile.TemporaryDirectory() as tmp:
        fixed = Path(tmp) / "fixed"
        trees.export_fixed(challenge, bare, fixed)
        trees.overlay_source(fixed, repo, m.existing_tests.test_paths)

    fixed_report = grader.grade(session.id)
    assert fixed_report.verdict == "PASS", grader.render_report(fixed_report)
    assert fixed_report.diff.changed_files == ["src/mistune/directives/toc.py", "src/mistune/toc.py"]

    assert "parent=state" in reveal.reveal_text(session.id)
    assert str(paths.home()) not in session.workspace  # workspaces live outside REPOMENTOR_HOME
