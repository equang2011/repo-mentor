"""Data models: challenge manifests, sessions, and grade reports.

Manifests are parsed strictly. A typo in a manifest should fail loudly at load
time, not silently change what the grader does.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from repomentor.errors import ManifestError

SCHEMA_VERSION = 1

KINDS = ("demo", "practice")
ORIGINS = ("upstream-fix", "synthetic")
DIFFICULTIES = ("easy", "medium", "hard")
PERMISSIVE_LICENSES = frozenset(
    {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "PSF-2.0", "0BSD"}
)

# The only manifest fields the CLI may ever print for a practice challenge
# outside `reveal`. A manifest's own `public_fields` must be a subset.
PUBLIC_FIELD_WHITELIST = frozenset(
    {"id", "kind", "repo.name", "difficulty", "time_budget_minutes", "python_version", "package.version"}
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_PRACTICE_ID_RE = re.compile(r"^p\d{2,}$")
_DEMO_ID_RE = re.compile(r"^demo-\d{3}$")
_AC_ID_RE = re.compile(r"^AC\d+$")


class _Reader:
    """Typed accessors over a JSON object that raise ManifestError with a field path."""

    def __init__(self, data: Any, where: str):
        if not isinstance(data, dict):
            raise ManifestError(f"{where}: expected a JSON object, got {type(data).__name__}")
        self.data = data
        self.where = where

    def _path(self, key: str) -> str:
        return f"{self.where}.{key}" if self.where else key

    def _get(self, key: str, required: bool) -> Any:
        if key not in self.data:
            if required:
                raise ManifestError(f"missing required field '{self._path(key)}'")
            return None
        return self.data[key]

    def str(self, key: str, required: bool = True, default: str | None = None) -> str | None:
        value = self._get(key, required)
        if value is None:
            return default
        if not isinstance(value, str) or not value.strip():
            raise ManifestError(f"'{self._path(key)}' must be a non-empty string")
        return value

    def int(self, key: str, required: bool = True, default: int | None = None) -> int | None:
        value = self._get(key, required)
        if value is None:
            return default
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ManifestError(f"'{self._path(key)}' must be a positive integer")
        return value

    def str_list(self, key: str, required: bool = True) -> list[str]:
        value = self._get(key, required)
        if value is None:
            return []
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise ManifestError(f"'{self._path(key)}' must be a list of non-empty strings")
        return list(value)

    def obj(self, key: str, required: bool = True) -> "_Reader | None":
        value = self._get(key, required)
        if value is None:
            return None
        return _Reader(value, self._path(key))

    def obj_list(self, key: str, required: bool = True) -> list["_Reader"]:
        value = self._get(key, required)
        if value is None:
            return []
        if not isinstance(value, list):
            raise ManifestError(f"'{self._path(key)}' must be a list")
        return [_Reader(item, f"{self._path(key)}[{i}]") for i, item in enumerate(value)]

    def choice(self, key: str, choices: tuple[str, ...]) -> str:
        value = self.str(key)
        if value not in choices:
            raise ManifestError(f"'{self._path(key)}' must be one of {', '.join(choices)}; got '{value}'")
        return value

    def sha(self, key: str) -> str:
        value = self.str(key)
        if not _SHA_RE.match(value):
            raise ManifestError(f"'{self._path(key)}' must be a full 40-character lowercase commit SHA")
        return value


@dataclass(frozen=True)
class RepoInfo:
    name: str
    url: str
    license: str  # SPDX id
    source_file_count: int
    source_count_command: str


@dataclass(frozen=True)
class PackageInfo:
    import_name: str  # used to prove grading imports the candidate's copy
    version: str  # package version at the buggy ref


@dataclass(frozen=True)
class InstallSpec:
    lock_file: str  # relative to the challenge directory
    pip_args: list[str]  # appended to `pip install --no-deps`, run from the repo root


@dataclass(frozen=True)
class Deselection:
    node_id: str
    reason: str


@dataclass(frozen=True)
class ExistingTests:
    pytest_args: list[str]  # e.g. ["tests"]; run from the repo root
    test_paths: list[str]  # files/dirs restored from the buggy ref before grading
    deselect: list[Deselection]
    timeout_seconds: int


@dataclass(frozen=True)
class PrivateTests:
    file: str  # relative to the challenge directory
    dest: str  # where it is placed inside the repo, so the repo's conftest applies
    timeout_seconds: int


@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str
    text: str
    tests: list[str]  # test names inside the private file, e.g. "test_foo" or "TestX::test_y"


@dataclass(frozen=True)
class Upstream:
    issue_url: str | None
    fix_url: str | None


@dataclass
class Manifest:
    id: str
    kind: str
    origin: str
    public_fields: list[str]
    repo: RepoInfo
    package: PackageInfo
    buggy_sha: str
    fixed_sha: str
    python_version: str
    install: InstallSpec
    existing_tests: ExistingTests
    private_tests: PrivateTests
    acceptance_criteria: list[AcceptanceCriterion]
    difficulty: str
    time_budget_minutes: int
    upstream: Upstream
    injection_patch: str | None = None  # synthetic only, relative to the challenge directory
    validation: dict[str, Any] | None = None
    schema_version: int = SCHEMA_VERSION

    @property
    def is_validated(self) -> bool:
        return bool(self.validation) and self.validation.get("status") == "passed"

    def public_view(self) -> dict[str, Any]:
        """Only whitelisted fields; safe to print for practice challenges."""
        flat = {
            "id": self.id,
            "kind": self.kind,
            "repo.name": self.repo.name,
            "difficulty": self.difficulty,
            "time_budget_minutes": self.time_budget_minutes,
            "python_version": self.python_version,
            "package.version": self.package.version,
        }
        allowed = PUBLIC_FIELD_WHITELIST & set(self.public_fields) | {"id"}
        return {k: v for k, v in flat.items() if k in allowed}

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data["injection_patch"] is None:
            del data["injection_patch"]
        return data

    @classmethod
    def from_dict(cls, data: Any) -> "Manifest":
        r = _Reader(data, "")
        version = r.int("schema_version")
        if version != SCHEMA_VERSION:
            raise ManifestError(f"unsupported schema_version {version}; this harness reads {SCHEMA_VERSION}")

        cid = r.str("id")
        kind = r.choice("kind", KINDS)
        if kind == "practice" and not _PRACTICE_ID_RE.match(cid):
            raise ManifestError(f"practice id '{cid}' must be opaque, like p01")
        if kind == "demo" and not _DEMO_ID_RE.match(cid):
            raise ManifestError(f"demo id '{cid}' must look like demo-001")
        origin = r.choice("origin", ORIGINS)

        public_fields = r.str_list("public_fields")
        extra = set(public_fields) - PUBLIC_FIELD_WHITELIST
        if extra:
            raise ManifestError(f"public_fields contains non-whitelisted fields: {', '.join(sorted(extra))}")

        repo_r = r.obj("repo")
        repo = RepoInfo(
            name=repo_r.str("name"),
            url=repo_r.str("url"),
            license=repo_r.str("license"),
            source_file_count=repo_r.int("source_file_count"),
            source_count_command=repo_r.str("source_count_command"),
        )
        pkg_r = r.obj("package")
        package = PackageInfo(import_name=pkg_r.str("import_name"), version=pkg_r.str("version"))

        inst_r = r.obj("install")
        install = InstallSpec(lock_file=inst_r.str("lock_file"), pip_args=inst_r.str_list("pip_args"))

        ex_r = r.obj("existing_tests")
        existing = ExistingTests(
            pytest_args=ex_r.str_list("pytest_args"),
            test_paths=ex_r.str_list("test_paths"),
            deselect=[
                Deselection(node_id=d.str("node_id"), reason=d.str("reason"))
                for d in ex_r.obj_list("deselect", required=False)
            ],
            timeout_seconds=ex_r.int("timeout_seconds", required=False, default=600),
        )
        if not existing.test_paths:
            raise ManifestError("'existing_tests.test_paths' must name at least one test path")

        pt_r = r.obj("private_tests")
        private = PrivateTests(
            file=pt_r.str("file"),
            dest=pt_r.str("dest"),
            timeout_seconds=pt_r.int("timeout_seconds", required=False, default=300),
        )

        criteria = [
            AcceptanceCriterion(id=a.str("id"), text=a.str("text"), tests=a.str_list("tests"))
            for a in r.obj_list("acceptance_criteria")
        ]
        _check_criteria(criteria)

        up_r = r.obj("upstream", required=False)
        upstream = Upstream(
            issue_url=up_r.str("issue_url", required=False) if up_r else None,
            fix_url=up_r.str("fix_url", required=False) if up_r else None,
        )

        injection = r.str("injection_patch", required=False)
        if origin == "synthetic" and not injection:
            raise ManifestError("synthetic challenges must set 'injection_patch'")

        validation = data.get("validation")
        if validation is not None and not isinstance(validation, dict):
            raise ManifestError("'validation' must be an object or null")

        return cls(
            id=cid,
            kind=kind,
            origin=origin,
            public_fields=public_fields,
            repo=repo,
            package=package,
            buggy_sha=r.sha("buggy_sha"),
            fixed_sha=r.sha("fixed_sha"),
            python_version=r.str("python_version"),
            install=install,
            existing_tests=existing,
            private_tests=private,
            acceptance_criteria=criteria,
            difficulty=r.choice("difficulty", DIFFICULTIES),
            time_budget_minutes=r.int("time_budget_minutes"),
            upstream=upstream,
            injection_patch=injection,
            validation=validation,
            schema_version=version,
        )


def _check_criteria(criteria: list[AcceptanceCriterion]) -> None:
    if not criteria:
        raise ManifestError("'acceptance_criteria' must contain at least one criterion")
    seen: set[str] = set()
    for ac in criteria:
        if not _AC_ID_RE.match(ac.id):
            raise ManifestError(f"acceptance criterion id '{ac.id}' must look like AC1")
        if ac.id in seen:
            raise ManifestError(f"duplicate acceptance criterion id '{ac.id}'")
        seen.add(ac.id)
        if not ac.tests:
            raise ManifestError(f"acceptance criterion {ac.id} maps to no private tests")


@dataclass
class Session:
    id: str
    challenge_id: str
    started_at: str  # ISO 8601, UTC
    workspace: str  # absolute path of the workspace root
    status: str = "attempted"  # attempted | passed
    last_grade: str | None = None  # ISO time of the last grade

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        return cls(**{k: data.get(k) for k in cls.__dataclass_fields__ if k in data})


@dataclass
class CriterionResult:
    id: str
    text: str
    passed: bool


@dataclass
class DiffStats:
    files_changed: int
    lines_added: int
    lines_removed: int
    changed_files: list[str]
    tests_modified: bool
    non_source_modified: bool


@dataclass
class GradeReport:
    session_id: str
    challenge_id: str
    graded_at: str
    elapsed_minutes: float
    criteria: list[CriterionResult]
    existing_passed: int
    existing_failed: int
    newly_failing: list[str]
    diff: DiffStats
    diagnosis_present: bool
    verdict: str  # PASS | FAIL
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
