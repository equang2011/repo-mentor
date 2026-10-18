"""Run pytest inside a challenge venv and collect per-node outcomes.

A tiny plugin (written to a temp dir and loaded with `-p`) records each node's outcome
and, for failures, the exception type. This is more reliable than parsing console
output, and it is how validation tells an assertion failure from an import error.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from repomentor import proc

PLUGIN_NAME = "repomentor_results_plugin"

PLUGIN_SOURCE = '''\
import json
import os

_results = {}


def _exc_type(report):
    """Exception class name from the crash line, e.g. 'KeyError: x' -> 'KeyError'."""
    crash = getattr(getattr(report, "longrepr", None), "reprcrash", None)
    message = (getattr(crash, "message", "") or "").strip()
    if not message:
        return None
    first = message.splitlines()[0].strip()
    if first.startswith("assert "):
        return "AssertionError"
    head = first.split(":", 1)[0].strip()
    if not head or " " in head:
        return None
    return head.rsplit(".", 1)[-1]


def pytest_runtest_logreport(report):
    entry = _results.setdefault(report.nodeid, {"outcome": "passed", "exc_type": None, "when": None})
    if entry["outcome"] != "passed":
        return
    if report.failed:
        entry["outcome"] = "failed" if report.when == "call" else "error"
        entry["exc_type"] = _exc_type(report)
        entry["when"] = report.when
    elif report.skipped:
        entry["outcome"] = "skipped"


def pytest_collectreport(report):
    if report.failed:
        _results[report.nodeid or "<collection>"] = {
            "outcome": "collection-error", "exc_type": _exc_type(report), "when": "collect"
        }


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("REPOMENTOR_RESULTS")
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"exitstatus": int(exitstatus), "results": _results}, fh)
'''

# pytest exit codes: 0 ok, 1 tests failed, 2 interrupted (e.g. collection errors),
# 3 internal error, 4 usage error, 5 no tests collected.
INTERNAL_EXIT_CODES = (3, 4)


@dataclass
class NodeResult:
    outcome: str  # passed | failed | error | skipped | collection-error
    exc_type: str | None = None


@dataclass
class PytestRun:
    exit_code: int
    timed_out: bool
    results: dict[str, NodeResult] = field(default_factory=dict)
    output_tail: str = ""
    results_missing: bool = False

    def failures(self) -> list[str]:
        return sorted(n for n, r in self.results.items() if r.outcome in ("failed", "error", "collection-error"))

    def passed(self) -> list[str]:
        return sorted(n for n, r in self.results.items() if r.outcome == "passed")

    def collection_errors(self) -> list[str]:
        return sorted(n for n, r in self.results.items() if r.outcome == "collection-error")

    @property
    def internal_error(self) -> bool:
        return self.timed_out is False and (self.exit_code in INTERNAL_EXIT_CODES or self.results_missing)


def run_pytest(
    python: Path, repo: Path, args: list[str], timeout: float, extra_env: dict[str, str] | None = None
) -> PytestRun:
    with tempfile.TemporaryDirectory(prefix="repomentor-pytest-") as tmp:
        tmp_path = Path(tmp)
        (tmp_path / f"{PLUGIN_NAME}.py").write_text(PLUGIN_SOURCE, encoding="utf-8")
        results_file = tmp_path / "results.json"
        # --rootdir pins node ids to repo-relative paths, matching manifests' test ids.
        cmd = [python, "-m", "pytest", "-p", PLUGIN_NAME, "-p", "no:cacheprovider", "-q",
               "--rootdir", str(repo), *args]
        result = proc.run(
            cmd,
            cwd=repo,
            timeout=timeout,
            env={"PYTHONPATH": str(tmp_path), "REPOMENTOR_RESULTS": str(results_file), **(extra_env or {})},
        )
        run = PytestRun(exit_code=result.returncode, timed_out=result.timed_out, output_tail=result.tail(40))
        if results_file.exists():
            data = json.loads(results_file.read_text(encoding="utf-8"))
            run.results = {k: NodeResult(v["outcome"], v.get("exc_type")) for k, v in data["results"].items()}
        elif not result.timed_out:
            run.results_missing = True
        return run


def node_matches(node_id: str, test_file: str, test_name: str) -> bool:
    """Does pytest node id `node_id` belong to test `test_name` in `test_file` (any parametrization)?"""
    base = f"{test_file}::{test_name}"
    return node_id == base or node_id.startswith(base + "[")
