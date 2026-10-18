"""Small units: diff stats, tree overlay, node matching, sessions, process env."""

from datetime import datetime, timezone

from repomentor import proc, sessions, trees
from repomentor.models import Session
from repomentor.pytest_runner import node_matches


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode())
    return p


def test_diff_stats_counts_lines_and_flags(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    write(a, "pkg/x.py", "one\ntwo\n")
    write(b, "pkg/x.py", "one\n2\nthree\n")
    write(a, "tests/t.py", "x\n")
    write(b, "tests/t.py", "y\n")
    write(b, "setup.cfg", "[x]\n")
    write(b, "pkg/__pycache__/x.pyc", "junk")
    stats = trees.diff_stats(a, b, ["tests"])
    assert stats.changed_files == ["pkg/x.py", "setup.cfg", "tests/t.py"]
    assert (stats.lines_added, stats.lines_removed) == (4, 2)
    assert stats.tests_modified and stats.non_source_modified


def test_diff_stats_ignores_line_ending_only_changes(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    write(a, "x.py", "one\ntwo\n")
    write(b, "x.py", "one\r\ntwo\r\n")
    assert trees.diff_stats(a, b, ["tests"]).files_changed == 0


def test_overlay_source_copies_and_deletes_but_keeps_tests(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    write(src, "pkg/a.py", "new")
    write(dst, "pkg/a.py", "old")
    write(dst, "pkg/gone.py", "x")
    write(dst, "tests/t.py", "mine")
    trees.overlay_source(src, dst, ["tests"])
    assert (dst / "pkg/a.py").read_text() == "new"
    assert not (dst / "pkg/gone.py").exists()
    assert (dst / "tests/t.py").read_text() == "mine"


def test_replace_paths_restores_and_removes_extras(tmp_path):
    pristine, cand = tmp_path / "p", tmp_path / "c"
    write(pristine, "tests/t.py", "orig")
    write(cand, "tests/t.py", "edited")
    write(cand, "tests/new.py", "extra")
    trees.replace_paths(cand, pristine, ["tests"])
    assert (cand / "tests/t.py").read_text() == "orig"
    assert not (cand / "tests/new.py").exists()


def test_node_matches():
    assert node_matches("tests/t.py::test_a", "tests/t.py", "test_a")
    assert node_matches("tests/t.py::test_a[1-2]", "tests/t.py", "test_a")
    assert node_matches("tests/t.py::TestX::test_a", "tests/t.py", "TestX::test_a")
    assert not node_matches("tests/t.py::test_ab", "tests/t.py", "test_a")


def test_session_status(isolated_home):
    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert sessions.status_for("demo-001") == "not started"
    sessions.save(Session(id="demo-001-a", challenge_id="demo-001", started_at=when.isoformat(), workspace="/x"))
    assert sessions.status_for("demo-001") == "attempted"
    sessions.save(Session(id="demo-001-b", challenge_id="demo-001", started_at=when.isoformat(),
                          workspace="/y", status="passed"))
    assert sessions.status_for("demo-001") == "passed"


def test_child_env_scrubs_python_path(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/stale/checkout")
    env = proc.child_env()
    assert "PYTHONPATH" not in env and env["PYTHONUTF8"] == "1"
