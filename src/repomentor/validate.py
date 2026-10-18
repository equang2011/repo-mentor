"""`validate`: prove a challenge is sound before it can be listed or started.

Checks run in order and stop at the first failure (see CLAUDE.md §7). The result is
written to the manifest's `validation` field; a failure de-lists the challenge.
"""

from __future__ import annotations

import contextlib
import os
import platform
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterator

from repomentor import __version__, envs, gitops, grader, leaks, proc, sessions, trees, workspace
from repomentor.challenges import Challenge, find_challenge, save_manifest
from repomentor.errors import RepoMentorError, ValidationError
from repomentor.models import PERMISSIVE_LICENSES, Manifest
from repomentor.pytest_runner import PytestRun, node_matches, run_pytest

SUITE_RUNS = 2
PRIVATE_RUNS = 3
DEFAULT_FAILURE_TYPES = frozenset({"AssertionError", "Failed"})  # Failed: pytest.fail / pytest.raises


@dataclass
class Check:
    step: int
    name: str
    detail: str


class _Fail(Exception):
    def __init__(self, step: int, name: str, message: str):
        super().__init__(message)
        self.step, self.name, self.message = step, name, message


@contextlib.contextmanager
def _throwaway_layout(root: Path) -> Iterator[None]:
    """Point sessions and workspaces at a temp dir for the end-to-end check."""
    saved = {k: os.environ.get(k) for k in ("REPOMENTOR_SESSIONS", "REPOMENTOR_WORKSPACES")}
    os.environ["REPOMENTOR_SESSIONS"] = str(root / "sessions")
    os.environ["REPOMENTOR_WORKSPACES"] = str(root / "workspaces")
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class Validator:
    def __init__(self, challenge: Challenge, log: Callable[[str], None]):
        self.challenge = challenge
        self.m: Manifest = challenge.manifest
        self.log = log
        self.checks: list[Check] = []
        self.python_full: str | None = None

    def ok(self, step: int, name: str, detail: str) -> None:
        self.checks.append(Check(step, name, detail))
        self.log(f"  [{step}] ok   {name}: {detail}")

    # -- step 1 ------------------------------------------------------------
    def check_repo(self) -> Path:
        step, name = 1, "repo, SHAs, license, files"
        m = self.m
        if m.repo.license not in PERMISSIVE_LICENSES:
            raise _Fail(step, name, f"license '{m.repo.license}' is not in the permissive list "
                                    f"({', '.join(sorted(PERMISSIVE_LICENSES))})")
        required = [self.challenge.ticket_path, self.challenge.lock_path, self.challenge.private_test_path,
                    self.challenge.solution_notes_path]
        if m.origin == "synthetic":
            required.append(self.challenge.directory / m.injection_patch)
        missing = [str(p.relative_to(self.challenge.directory)) for p in required if not p.is_file()]
        if missing:
            raise _Fail(step, name, f"missing challenge files: {', '.join(missing)}")
        ticket = self.challenge.ticket_path.read_text(encoding="utf-8")
        absent = [ac.id for ac in m.acceptance_criteria if ac.id not in ticket]
        if absent:
            raise _Fail(step, name, f"ticket.md does not mention {', '.join(absent)}")
        try:
            bare = gitops.ensure_repo(m.repo.url, [m.buggy_sha, m.fixed_sha])
        except RepoMentorError as exc:
            raise _Fail(step, name, str(exc)) from None
        if m.origin == "upstream-fix" and m.buggy_sha not in gitops.parents(bare, m.fixed_sha):
            raise _Fail(step, name, "buggy_sha must be a parent of fixed_sha (the commit just before the fix)")
        if m.origin == "synthetic" and m.buggy_sha != m.fixed_sha:
            raise _Fail(step, name, "synthetic challenges use the clean commit as both buggy_sha and fixed_sha")
        self.ok(step, name, f"{m.repo.license}, buggy {m.buggy_sha[:10]}, fixed {m.fixed_sha[:10]}")
        return bare

    # -- step 2 ------------------------------------------------------------
    def build_env(self, venv: Path, repo: Path) -> Path:
        step, name = 2, "fresh venv from lock"
        try:
            python = envs.build_env(
                venv, self.m.python_version, self.challenge.lock_path, repo, self.m.install.pip_args, self.m.install.env
            )
        except RepoMentorError as exc:
            raise _Fail(step, name, str(exc)) from None
        version = proc.run([python, "-c", "import platform; print(platform.python_version())"], timeout=60)
        self.python_full = version.stdout.strip() or None
        self.ok(step, name, f"Python {self.python_full}, {self.challenge.lock_path.name}")
        return python

    def _reinstall(self, step: int, name: str, python: Path, repo: Path) -> None:
        try:
            envs.install_package(python, repo, self.m.install.pip_args, self.m.install.env)
            grader.assert_imports_from(python, repo, self.m)
        except RepoMentorError as exc:
            raise _Fail(step, name, str(exc)) from None

    def _suite(self, python: Path, repo: Path) -> PytestRun:
        return run_pytest(python, repo, grader.existing_suite_args(self.m), self.m.existing_tests.timeout_seconds)

    # -- steps 3, 4 --------------------------------------------------------
    def check_suite(self, step: int, name: str, python: Path, repo: Path, runs: int, hint: str) -> None:
        self._reinstall(step, name, python, repo)
        for i in range(1, runs + 1):
            run = self._suite(python, repo)
            if run.timed_out:
                raise _Fail(step, name, f"run {i} timed out after {self.m.existing_tests.timeout_seconds}s")
            failing = run.failures()
            if run.exit_code != 0 or failing:
                shown = "\n    ".join(failing[:20]) or f"(no failing nodes; pytest exit {run.exit_code})"
                raise _Fail(step, name, f"run {i}: existing tests fail:\n    {shown}\n{hint}\n"
                                        f"pytest output:\n{run.output_tail}")
        self.ok(step, name, f"{len(run.passed())} passed x{runs}")

    # -- steps 5, 6 --------------------------------------------------------
    def check_private(self, step: int, name: str, python: Path, repo: Path, at_buggy: bool) -> None:
        self._reinstall(step, name, python, repo)
        dest = self.m.private_tests.dest.replace("\\", "/")
        allowed = DEFAULT_FAILURE_TYPES | {e.type for e in self.m.private_tests.allowed_exceptions}
        for i in range(1, PRIVATE_RUNS + 1):
            run = run_pytest(python, repo, [dest], self.m.private_tests.timeout_seconds)
            if run.timed_out:
                raise _Fail(step, name, f"run {i}: private tests timed out")
            if run.collection_errors():
                raise _Fail(step, name, f"run {i}: private tests had collection errors "
                                        f"(an import or syntax problem, not a behavioral failure):\n{run.output_tail}")
            self._check_mapping(step, name, run, dest)
            for ac in self.m.acceptance_criteria:
                for test in ac.tests:
                    for node, res in run.results.items():
                        if not node_matches(node, dest, test):
                            continue
                        expect_pass = (not at_buggy) or ac.guard
                        if expect_pass and res.outcome != "passed":
                            why = "guard tests must pass at the buggy ref" if at_buggy else "must pass at the fixed ref"
                            raise _Fail(step, name, f"run {i}: {node} ({ac.id}) {res.outcome}; {why}")
                        if not expect_pass:
                            if res.outcome != "failed":
                                raise _Fail(step, name, f"run {i}: {node} ({ac.id}) {res.outcome} at the buggy ref; "
                                                        "it must fail with a test failure")
                            if res.exc_type not in allowed:
                                raise _Fail(step, name, f"run {i}: {node} ({ac.id}) failed with {res.exc_type}, "
                                                        "not an assertion. Add it to private_tests.allowed_exceptions "
                                                        "with a reason if it is the behavioral symptom.")
        where = "buggy" if at_buggy else "fixed"
        self.ok(step, name, f"{len(run.results)} private tests as expected at the {where} ref x{PRIVATE_RUNS}")

    def _check_mapping(self, step: int, name: str, run: PytestRun, dest: str) -> None:
        mapped = [(ac.id, t) for ac in self.m.acceptance_criteria for t in ac.tests]
        for ac_id, test in mapped:
            if not any(node_matches(n, dest, test) for n in run.results):
                raise _Fail(step, name, f"{ac_id} maps to '{test}', which was not collected from {dest}")
        orphans = [n for n in run.results if not any(node_matches(n, dest, t) for _, t in mapped)]
        if orphans:
            raise _Fail(step, name, f"private tests not mapped to any criterion: {', '.join(orphans)}")

    # -- steps 7, 8 --------------------------------------------------------
    def check_end_to_end(self, fixed_tree: Path, scratch: Path) -> None:
        step, name = 7, "end to end: start, grade untouched (FAIL), overlay fix, grade (PASS)"
        with _throwaway_layout(scratch):
            try:
                session = workspace.start(self.m.id, allow_unvalidated=True)
            except RepoMentorError as exc:
                raise _Fail(step, name, f"start failed: {exc}") from None
            leak_problems = leaks.check_workspace(Path(session.workspace), self.challenge)
            try:
                untouched = grader.grade(session.id)
                if untouched.verdict != "FAIL":
                    raise _Fail(step, name, "grading the untouched workspace reported PASS")
                bad = [c.id for c, ac in zip(untouched.criteria, self.m.acceptance_criteria) if c.passed != ac.guard]
                if bad or untouched.newly_failing:
                    raise _Fail(step, name, f"untouched grade is FAIL for the wrong reasons: criteria {bad}, "
                                            f"newly failing {untouched.newly_failing}")
                trees.overlay_source(fixed_tree, Path(session.workspace) / "repo", self.m.existing_tests.test_paths)
                fixed = grader.grade(session.id)
                if fixed.verdict != "PASS":
                    raise _Fail(step, name, "grading with the fixed ref's source reported FAIL:\n"
                                            + grader.render_report(fixed))
            except RepoMentorError as exc:
                raise _Fail(step, name, f"grader error: {exc}") from None
        self.ok(step, name, "untouched FAIL, fixed PASS")

        step, name = 8, "leak check"
        if leak_problems:
            raise _Fail(step, name, "workspace leaks:\n    " + "\n    ".join(leak_problems))
        self.ok(step, name, "one commit, no private files, no upstream references")

    # -- driver ------------------------------------------------------------
    def run(self) -> None:
        bare = self.check_repo()
        with tempfile.TemporaryDirectory(prefix="repomentor-validate-") as tmp:
            tmp_path = Path(tmp)
            buggy = tmp_path / "buggy"
            trees.export_buggy(self.challenge, bare, buggy)
            fixed_src = tmp_path / "fixed-src"
            trees.export_fixed(self.challenge, bare, fixed_src)
            # Fixed source + the buggy ref's tests: exactly what grading sees for a correct fix.
            fixed = tmp_path / "fixed"
            trees.copy_tree(fixed_src, fixed)
            trees.replace_paths(fixed, buggy, self.m.existing_tests.test_paths)

            python = self.build_env(tmp_path / "venv", buggy)
            self.check_suite(3, "existing suite at buggy ref", python, buggy, SUITE_RUNS,
                             "Deselect environment-specific failures with a reason, or reject the challenge.")
            self.check_suite(4, "buggy ref's suite against fixed source", python, fixed, 1,
                             "If the fix changed a test because it encoded the buggy behavior, deselect it "
                             "with that reason or reject the challenge.")
            for tree in (buggy, fixed):
                dest = tree / self.m.private_tests.dest
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.challenge.private_test_path, dest)
            self.check_private(5, "private tests fail at buggy ref", python, buggy, at_buggy=True)
            self.check_private(6, "private tests pass at fixed ref", python, fixed, at_buggy=False)
            self.check_end_to_end(fixed_src, tmp_path / "e2e")


def validate(challenge_id: str, log: Callable[[str], None] = print) -> list[Check]:
    challenge = find_challenge(challenge_id)
    log(f"Validating {challenge.id}")
    v = Validator(challenge, log)
    started = sessions.now_utc().isoformat()

    def record(status: str, **extra) -> None:
        challenge.manifest.validation = {
            "status": status, "validated_at": started, "python": v.python_full,
            "platform": platform.platform(), "harness_version": __version__,
            **extra, "checks": [asdict(c) for c in v.checks],
        }
        save_manifest(challenge)

    try:
        v.run()
    except _Fail as fail:
        record("failed", failed_step=fail.step)
        raise ValidationError(f"step {fail.step} ({fail.name}) failed: {fail.message}") from None
    record("passed")
    log(f"{challenge.id}: validation passed")
    return v.checks

