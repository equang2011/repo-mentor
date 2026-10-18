"""`grade`: evaluate a candidate's workspace against the private regression tests.

Isolation steps, in order:
  1. Copy the candidate's repo (minus .git, venvs, caches) into a fresh temp dir.
  2. Restore pristine copies of the existing test paths from the buggy ref, so edited
     tests can't change the result; new test files there disappear with them.
  3. Add the private tests, build a fresh venv, install the package from the temp copy.
  4. Probe, through pytest itself, where the package is imported from. Refuse to grade
     unless it is the temp copy (catches stale installs and stray paths).
  5. Run the private tests and the existing suite, each with a timeout.

The report names acceptance criteria and visible existing tests only, never private
test names, code, or tracebacks.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from repomentor import envs, gitops, sessions, trees
from repomentor.challenges import Challenge, find_challenge
from repomentor.errors import GraderError, RepoMentorError, ToolError, WorkspaceError
from repomentor.models import CriterionResult, GradeReport, Manifest
from repomentor.pytest_runner import PytestRun, node_matches, run_pytest
from repomentor.workspace import DIAGNOSIS_TEMPLATE, LEGACY_DIAGNOSIS_TEMPLATES

PROBE_FILE = "test_zz_repomentor_probe.py"
PROBE_SOURCE = '''\
import importlib.util
import json
import os


def test_repomentor_import_probe():
    spec = importlib.util.find_spec(os.environ["REPOMENTOR_PROBE_MODULE"])
    with open(os.environ["REPOMENTOR_PROBE_OUT"], "w", encoding="utf-8") as fh:
        json.dump({"origin": spec.origin if spec else None}, fh)
'''


def _same_or_inside(child: Path, parent: Path) -> bool:
    c = os.path.normcase(str(child.resolve()))
    p = os.path.normcase(str(parent.resolve()))
    return c == p or c.startswith(p.rstrip("\\/") + os.sep)


def assert_imports_from(python: Path, repo: Path, manifest: Manifest, timeout: float = 120) -> Path:
    """Prove that, under the repo's own pytest config, the package resolves inside `repo`."""
    name = manifest.package.import_name
    dest_dir = (repo / manifest.private_tests.dest).parent
    probe = dest_dir / PROBE_FILE
    out = repo.parent / "probe.json"
    probe.write_text(PROBE_SOURCE, encoding="utf-8")
    try:
        run = run_pytest(
            python, repo, [probe.relative_to(repo).as_posix()], timeout,
            extra_env={"REPOMENTOR_PROBE_MODULE": name, "REPOMENTOR_PROBE_OUT": str(out)},
        )
    finally:
        probe.unlink(missing_ok=True)
    if not out.exists():
        raise GraderError(
            f"could not determine where '{name}' is imported from (probe exit code {run.exit_code}). "
            f"Output:\n{run.output_tail}"
        )
    origin = json.loads(out.read_text(encoding="utf-8"))["origin"]
    if not origin:
        raise GraderError(f"'{name}' is not importable in the grading environment")
    if not _same_or_inside(Path(origin), repo):
        raise GraderError(
            f"grading would import '{name}' from {origin}, not from the candidate copy in {repo}. "
            "Refusing to grade against stale code."
        )
    return Path(origin)


def evaluate_criteria(manifest: Manifest, run: PytestRun) -> list[CriterionResult]:
    dest = manifest.private_tests.dest.replace("\\", "/")
    results = []
    for ac in manifest.acceptance_criteria:
        ok = True
        for test in ac.tests:
            nodes = [r for n, r in run.results.items() if node_matches(n, dest, test)]
            if not nodes or any(r.outcome != "passed" for r in nodes):
                ok = False
        results.append(CriterionResult(id=ac.id, text=ac.text, passed=ok))
    return results


def diagnosis_status(ws: Path) -> str:
    path = ws / "diagnosis.md"
    if not path.is_file():
        return "missing"
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    templates = {t.strip() for t in (DIAGNOSIS_TEMPLATE, *LEGACY_DIAGNOSIS_TEMPLATES)}
    return "template only (not filled in)" if text.strip() in templates else "present"


def _deselect_args(manifest: Manifest) -> list[str]:
    args: list[str] = []
    for d in manifest.existing_tests.deselect:
        args += ["--deselect", d.node_id]
    return args


def existing_suite_args(manifest: Manifest) -> list[str]:
    return [*manifest.existing_tests.pytest_args, *_deselect_args(manifest),
            "--ignore", manifest.private_tests.dest]


def grade(session_id: str, *, when: datetime | None = None) -> GradeReport:
    session = sessions.load(session_id)
    challenge = find_challenge(session.challenge_id)
    ws = Path(session.workspace)
    repo = ws / "repo"
    if not repo.is_dir():
        raise WorkspaceError(f"the workspace repo {repo} no longer exists; start a new session")

    with tempfile.TemporaryDirectory(prefix="repomentor-grade-") as tmp:
        report = _grade_in(Path(tmp), session, challenge, repo, ws, when or sessions.now_utc())

    _save_report(report)
    if report.verdict == "PASS":
        session.status = "passed"
    session.last_grade = report.graded_at
    sessions.save(session)
    return report


def _grade_in(tmp: Path, session, challenge: Challenge, repo: Path, ws: Path, when: datetime) -> GradeReport:
    m = challenge.manifest
    test_paths = m.existing_tests.test_paths
    notes: list[str] = []

    try:
        bare = gitops.ensure_repo(m.repo.url, [m.buggy_sha])
        pristine = tmp / "pristine"
        trees.export_buggy(challenge, bare, pristine)
    except ToolError as exc:
        raise GraderError(f"could not export the pristine buggy ref: {exc}") from None

    candidate = tmp / "repo"
    trees.copy_tree(repo, candidate)
    diff = trees.diff_stats(pristine, candidate, test_paths)
    trees.replace_paths(candidate, pristine, test_paths)
    dest = candidate / m.private_tests.dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(challenge.private_test_path, dest)

    try:
        python = envs.create_venv(tmp / "venv", m.python_version)
        envs.install_lock(python, challenge.lock_path)
    except RepoMentorError as exc:
        raise GraderError(f"could not build the grading environment: {exc}") from None

    criteria: list[CriterionResult]
    existing_passed = existing_failed = 0
    newly_failing: list[str] = []
    try:
        envs.install_package(python, candidate, m.install.pip_args, m.install.env)
    except WorkspaceError as exc:
        notes.append(f"Your copy of the package failed to install, so no tests could run.\n{exc}")
        criteria = [CriterionResult(ac.id, ac.text, False) for ac in m.acceptance_criteria]
    else:
        assert_imports_from(python, candidate, m)
        private = run_pytest(python, candidate, [m.private_tests.dest], m.private_tests.timeout_seconds)
        if private.internal_error:
            raise GraderError(f"pytest failed internally on the private tests (exit {private.exit_code})")
        if private.timed_out:
            notes.append(f"Private tests timed out after {m.private_tests.timeout_seconds}s.")
        elif private.collection_errors():
            notes.append("Private tests could not be collected (usually an error raised while importing the package).")
        criteria = evaluate_criteria(m, private)

        existing = run_pytest(python, candidate, existing_suite_args(m), m.existing_tests.timeout_seconds)
        if existing.internal_error:
            raise GraderError(f"pytest failed internally on the existing suite (exit {existing.exit_code})")
        existing_passed = len(existing.passed())
        # Validation proved the whole suite passes at the buggy ref, so any failure is new.
        newly_failing = existing.failures()
        existing_failed = len(newly_failing)
        if existing.timed_out:
            notes.append(f"The existing test suite timed out after {m.existing_tests.timeout_seconds}s.")
            newly_failing = newly_failing or ["<existing suite timed out>"]

    if diff.tests_modified:
        notes.append("You modified existing test files. Grading used the original versions.")
    if diff.non_source_modified:
        notes.append("You modified non-Python files; check that this was intended.")

    started = datetime.fromisoformat(session.started_at)
    verdict = "PASS" if all(c.passed for c in criteria) and not newly_failing else "FAIL"
    return GradeReport(
        session_id=session.id,
        challenge_id=m.id,
        graded_at=when.isoformat(),
        elapsed_minutes=round((when - started).total_seconds() / 60, 1),
        criteria=criteria,
        existing_passed=existing_passed,
        existing_failed=existing_failed,
        newly_failing=newly_failing,
        diff=diff,
        diagnosis=diagnosis_status(ws),
        verdict=verdict,
        notes=notes,
    )


def _save_report(report: GradeReport) -> Path:
    d = sessions.session_dir(report.session_id) / "grades"
    d.mkdir(parents=True, exist_ok=True)
    stamp = report.graded_at.replace(":", "").replace("+0000", "Z")
    path = d / f"grade-{stamp}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    (d / "latest.txt").write_text(render_report(report), encoding="utf-8")
    return path


def render_report(report: GradeReport, budget_minutes: int | None = None) -> str:
    lines = [
        f"RepoMentor grade report: session {report.session_id} ({report.challenge_id})",
        f"Elapsed since start: {report.elapsed_minutes} min"
        + (f" (budget {budget_minutes} min)" if budget_minutes else ""),
        "",
        "Acceptance criteria:",
    ]
    for c in report.criteria:
        lines.append(f"  {c.id:<4} {'PASS' if c.passed else 'FAIL'}  {c.text}")
    lines += ["", f"Existing tests: {report.existing_passed} passed, {report.existing_failed} failed"]
    for node in report.newly_failing:
        lines.append(f"  now failing: {node}")
    d = report.diff
    lines += ["", f"Your changes: {d.files_changed} file(s), +{d.lines_added} -{d.lines_removed}"]
    for f in d.changed_files:
        lines.append(f"  {f}")
    lines.append(f"diagnosis.md: {report.diagnosis}")
    if report.notes:
        lines += ["", "Notes:"] + [f"  - {n}" for n in report.notes]
    lines += ["", f"VERDICT: {report.verdict}"]
    return "\n".join(lines) + "\n"
