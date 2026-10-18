"""`reveal`: the answer key, only on explicit request."""

from __future__ import annotations

import tempfile
from pathlib import Path

from repomentor import gitops, sessions, trees
from repomentor.challenges import Challenge, find_challenge


def source_fix_diff(challenge: Challenge) -> str:
    """The real fix: upstream's source diff, or the reversed injection patch for synthetic ones."""
    m = challenge.manifest
    bare = gitops.ensure_repo(m.repo.url, [m.buggy_sha, m.fixed_sha])
    if m.origin == "upstream-fix":
        return gitops.diff_source(bare, m.buggy_sha, m.fixed_sha, m.existing_tests.test_paths)
    with tempfile.TemporaryDirectory(prefix="repomentor-reveal-") as tmp:
        buggy, clean = Path(tmp) / "buggy", Path(tmp) / "fixed"
        trees.export_buggy(challenge, bare, buggy)
        trees.export_fixed(challenge, bare, clean)
        result = gitops.git("diff", "--no-index", "--no-color", "buggy", "fixed", cwd=Path(tmp), check=False)
        return result.stdout


def reveal_text(session_id: str) -> str:
    session = sessions.load(session_id)
    challenge = find_challenge(session.challenge_id)
    m = challenge.manifest
    parts = [f"Answer key for {m.id} ({m.repo.name}, {m.origin})", ""]
    if challenge.solution_notes_path.is_file():
        parts += [challenge.solution_notes_path.read_text(encoding="utf-8"), ""]
    parts += ["Upstream links:"]
    parts += [f"  issue: {m.upstream.issue_url or '-'}", f"  fix:   {m.upstream.fix_url or '-'}", ""]
    parts += ["Source diff of the real fix (tests excluded):", source_fix_diff(challenge)]
    return "\n".join(parts)
