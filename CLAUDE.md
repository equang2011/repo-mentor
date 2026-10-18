# RepoMentor Debug Gym — Project Instructions

This file is the standing brief for every Claude Code session in this repository. Read it fully before doing anything.

## 0. Which session is this?

Work happens in two kinds of sessions. Do only the one the user names. If no session is named, treat the work as ordinary harness work under Session 1 rules, and never create, inspect, or describe practice challenges.

- **Session 1 — Harness build (attended).** I watch and review everything. It builds the tool and one demo challenge that I'm allowed to fully understand. See §11.
- **Session 2 — Practice-challenge authoring (unattended).** It runs headless while I'm away and creates the practice challenges I will later solve without knowing the answers. See §12.

The spoiler rules in §3 apply to every session.

## 1. Project context

I'm building **RepoMentor Debug Gym**, a local Python CLI for practicing repository-based debugging interviews. My interview is in 5–6 weeks, so a working tool soon beats an elegant tool later.

The interview format, as described to me secondhand by someone who interviews there (informal, not official requirements):

- An unfamiliar Python repository of about 30 source files.
- A customer-reported bug delivered as a Jira-style ticket.
- A simple, slow AI coding assistant available during the exercise.
- The candidate navigates the repo, reproduces and diagnoses the bug, makes a targeted fix, and explains the investigation, the fix, and how they tested it.

Grading procedures, timing, and difficulty in this tool are our own design assumptions. The product simulates real engineering work, not LeetCode problems.

## 2. User experience

```bash
repomentor list                  # practice challenges, no spoilers
repomentor start p03             # creates a fresh workspace, prints its path and session id
# ... I investigate and fix in the workspace with my editor, terminal, and a limited assistant ...
repomentor grade <session_id>    # runs hidden checks against my copy, prints a report
repomentor reveal <session_id>   # optional, after I'm done: shows the answer key
```

`python -m repomentor ...` works too.

The workspace contains the buggy repository (with no git history), `ticket.md`, a `diagnosis.md` template, and short instructions for setting up and running tests. Each challenge targets 30–60 minutes for a developer with 1–2 years of Python experience.

`diagnosis.md` is optional. Its headings are: root-cause hypothesis, supporting evidence, what I changed, and how I verified it. The grader reports whether the file exists and does not evaluate its contents.

## 3. Spoiler rules (all sessions)

I will solve the practice challenges myself, so their answers must never reach me before I run `reveal`.

For any practice challenge, never put any of the following in chat replies, final output, commit messages, CLAUDE.md, auto memory, or any file inside this repository:

- the defective file, function, line, or module;
- the root cause or the fix, including hints ("look at the parser");
- private test code, or what the private tests check beyond the ticket's acceptance criteria;
- upstream issue numbers, titles, URLs, or fix-commit SHAs.

Practice-challenge data lives only in the pack directory (`$REPOMENTOR_HOME/pack/`, default `~/.repomentor/pack/`), outside this repository. Harness tests use the demo challenge or synthetic fixtures, never the pack. The CLI prints only whitelisted, spoiler-free fields from practice manifests, except in `reveal`.

**The demo challenge is exempt.** In Session 1, explain it to me in full; it exists so I can learn how challenges are built.

If I ask in chat to see practice-challenge internals, remind me of these rules and ask me to confirm before showing anything, and suggest `repomentor reveal` instead.

## 4. Approach

**Challenges come from real upstream bug fixes.** For a chosen repo, find a closed issue with a merged fix that added or changed a test. Then:

- the **buggy ref** is the commit just before the fix, and the workspace is built from it;
- the **fixed ref** is the fix commit, used only for validation;
- the **private regression tests** are derived from the tests that shipped with the fix, adapted per §6;
- the **ticket** is rewritten from the issue per §6.

Real fixes give realistic bugs and a known-correct repair. They also can't leak through history, because the workspace has no history and the buggy ref predates the fix.

**Synthetic fallback.** If a practice repo has too few suitable fixes, a challenge may instead use a hand-injected defect on a clean commit. It must be a plausible regression (a boundary condition, a wrong default, state not reset, a filter or transformation that is wrong for one combination of inputs). It must never be a syntax error, an obvious crash, a dependency break, or broken setup instructions. At most a third of the pack may be synthetic. The injection patch is stored privately, and the clean commit serves as the fixed ref.

**Target pack:** 6–10 validated practice challenges across 2–3 repos, with a mix of difficulties, at most 4 per repo, and no two in the same function. Separately, one demo challenge from a different repo.

## 5. Repository selection criteria

- Public, with a permissive license (MIT, BSD, Apache-2.0). Record the SPDX id.
- 20–60 non-test Python source files in the package, excluding tests, docs, examples, benchmarks, and build scripts. Record the count and the command used to get it.
- An existing pytest suite that passes on my local Python in under about 2 minutes, with no network, external services, or GPU.
- Dependencies installable from PyPI without compilers.
- A domain that's understandable without specialist knowledge, with real interaction between modules.
- A history of fix commits linked to issues.
- Practice repos must differ from the demo repo. Prefer variety, for example a CLI tool, a parsing or transformation library, and something stateful.
- Practice repos must not share a domain with the demo repo. The demo is mistune (a Markdown parser), so no other Markdown parsers or renderers.

For every challenge, record the repo URL, license, full commit SHAs, Python version, and a pinned dependency lock (`pip freeze` at the buggy ref).

## 6. Challenge contents

Each challenge directory looks like this:

```text
<challenge-id>/
├── manifest.json
├── ticket.md
├── lock.txt
└── private/
    ├── test_regression.py
    ├── solution_notes.md     # root cause, fix summary, upstream links, repro outputs
    └── injection.patch       # synthetic challenges only
```

Practice IDs are opaque (`p01`, `p02`, …). The demo is `demo-001` and lives in this repo under `demo/`.

**manifest.json** includes at least: id; kind (demo or practice); origin (upstream-fix or synthetic); repo URL; license; buggy and fixed SHAs; Python version; install steps; the existing-test command; any deselected existing tests, each with a reason; the acceptance criteria (id, text, a `guard` flag, and the private test node ids each one maps to); estimated difficulty; time budget in minutes; and validation results. Mark which fields are public. Everything else is private.

**ticket.md** is written as a customer who uses the library or CLI:

- A title, the environment (package version at the buggy ref and Python version), and a short summary.
- Steps to reproduce, using only the CLI or a short script (15 lines or fewer) that uses the public API.
- Expected behavior, actual behavior (real output captured at the buggy ref), and input/output examples.
- Acceptance criteria labeled AC1…ACn, each behavioral and testable.
- It never names internal files, modules, or functions, the root cause, or the fix. Public API names a user would type are fine.
- Paraphrase; never copy the upstream issue. Change incidental example values so the ticket can't be found by searching its text. Then confirm the repro still shows the bug at the buggy ref and not at the fixed ref, and record both outputs in solution_notes.md.

**Private regression tests:**

- Exercise only public interfaces that exist at the buggy ref. Never import helpers that the fix introduced.
- Assert the behavior described in the acceptance criteria, not implementation details, so any correct fix passes.
- Include at least one variant of the ticket's example with different values, so a fix that special-cases the example fails.
- Include nearby cases that already work, so a fix that breaks neighboring behavior fails. Put these under a **guard** acceptance criterion (`"guard": true` in the manifest), written in the ticket as behavior that must not change (for example "AC3: nothing else changes: …").
- Guard and non-guard criteria are separate: every test belongs to exactly one criterion. Tests under a non-guard criterion target the bug and must fail at the buggy ref. Tests under a guard criterion must pass at both refs. At least one criterion must be non-guard.
- Every non-guard acceptance criterion must have at least one test that fails at the buggy ref, so that criterion actually detects the bug.
- Be deterministic, offline, and fast (seconds).
- Run under the repo's own pytest configuration and fixtures.

## 7. Validation

`repomentor validate <challenge-id>` must pass before a challenge is listed. It stops at the first unmet check with a clear, actionable message:

1. The repo and both SHAs resolve, and the license is recorded and permissive.
2. A fresh venv installs from lock.txt on the local Python.
3. The existing suite passes at the buggy ref (minus documented deselections), on two runs.
4. The buggy ref's existing suite also passes against the fixed ref's source. If the upstream fix changed an existing test because that test encoded the buggy behavior, deselect it with that reason or reject the challenge.
5. At the buggy ref, every test under a non-guard criterion fails with a test failure (an assertion), not a collection, import, or fixture error. This also guarantees that every non-guard criterion has at least one failing test. Another exception type is allowed only if the manifest explains why it is the behavioral symptom (`private_tests.allowed_exceptions`). Every test under a guard criterion passes at the buggy ref, which proves it is a real guard and not a hidden bug check. Every private test must map to exactly one criterion; unmapped tests fail validation.
6. Every private test, guard or not, passes at the fixed ref. Steps 5 and 6 each run three times to catch flakiness.
7. End to end: `start` a throwaway session and `grade` it untouched, which must report FAIL. Then overlay the fixed ref's source and `grade` again, which must report PASS. This proves grading imports the candidate's copy and not some stale install.
8. Leak check: the workspace has a single-commit git history, no private files, and no upstream issue number or URL.

## 8. Workspaces and grading

No Docker in this version. I'm the only candidate and the source repos are vetted public projects, so isolation means separate directories and separate venvs. This is a spoiler boundary, not a security sandbox; the README should say so.

**start**

- Export the buggy ref with no history (for example with `git archive`) into `~/repomentor-workspaces/<session-id>/repo/`.
- Run `git init` and make one "Initial snapshot" commit, so I can use `git diff` on my own changes.
- Add ticket.md, the diagnosis.md template, and a short README.
- Create `.venv` in the workspace, install from the lock, and install the package in editable mode.
- Record session metadata (id, challenge id, start time, path) under `$REPOMENTOR_HOME/sessions/`.
- Give clear errors for: unknown challenge, unvalidated challenge, workspace already exists, git or Python missing, and install failure (show the tail of the pip output).

**grade**

- Copy the candidate's repo (excluding `.venv`, `.git`, and caches) to a fresh temporary directory.
- Restore pristine copies of the existing test files from the buggy ref, so edits to tests can't change the result. New test files the candidate added are ignored.
- Add the private tests and install into a grading venv. **Before running anything, assert that the package imports from the temporary directory.**
- Run the private tests and the existing suite, with timeouts.
- Report:
  - each acceptance criterion as PASS or FAIL (never private test code, names, or tracebacks);
  - for the existing suite, pass/fail counts and the node ids of existing tests that now fail (these tests are visible, so naming them is fine);
  - diff stats against the snapshot: files changed, lines added and removed, and a flag if tests or non-source files were modified;
  - elapsed time since `start`;
  - whether diagnosis.md is present (not evaluated) or missing;
  - an overall verdict, which is PASS only if every criterion passes and no existing test newly fails.
- Save the report in the session directory, and exit non-zero on FAIL or on grader error. Clearly distinguish "your fix failed" from "the grader itself failed."

**reveal** asks for confirmation, then prints solution_notes.md, the upstream issue and PR links, and the fixed ref's diff of source files (or the reversed injection patch for synthetic challenges), so I can compare my fix with the real one.

**list** shows the id, source repo name, estimated difficulty, time budget, and my status (not started, attempted, or passed). Nothing else.

## 9. Engineering style and what I review

Handle scaffolding, packaging, CLI plumbing, and straightforward tests yourself. I want to understand and weigh in on: repository selection, the challenge format, the validation checks and how they can fail, workspace and grading isolation, and grading correctness. Briefly explain meaningful design choices and tradeoffs.

- Python 3.10+, standard library plus pytest. Ask before adding any other runtime dependency.
- Readable code, small functions, type hints where useful, and dataclasses for models.
- Explicit exception types (for example ChallengeError, ValidationError, WorkspaceError, GraderError) with actionable messages.
- `subprocess` with argument lists and timeouts; no `shell=True`.
- Deterministic behavior. Tests use a temporary `REPOMENTOR_HOME`.
- Small, reviewable commits.

## 10. Non-goals

Do not build any of these: a web UI, authentication, accounts, payments, databases, embeddings or retrieval-augmented generation, multi-agent frameworks, LLM-based grading, Docker or other sandboxing (deferred), plugin systems, generating challenges from arbitrary repos at runtime (authoring is an offline, curated step), integration with my LLM Gateway, or hosting.

## 11. Session 1 — Harness build (attended)

Spoilers are allowed for the demo challenge only. Do not choose practice repos or create practice challenges.

A. Inspect the directory. Don't overwrite existing work.

B. Build the skeleton: an installable package, `pyproject.toml`, pytest setup, `python -m repomentor` plus a `repomentor` console script, the models, and a README with install instructions and a short practice protocol (see below).

C. Demo repo: propose 2–3 candidates against §5 with a short tradeoff comparison, and **wait for my choice**. Then pin it, set up the environment, run the baseline, and report the repo, SHA, license, source file count, and baseline results.

D. Build the demo challenge `demo-001` from one upstream fix, following §4–§6. Walk me through the defect, the ticket, and your test design choices in full.

E. Implement `validate`, `start`, `grade`, `list`, and `reveal`. Run `validate demo-001` end to end.

F. Write tests: unit tests for manifest loading and models; failure-mode tests (unknown challenge, bad manifest, existing workspace, leak check, and detecting that grading ran against stale code); and one integration test that runs the full demo lifecycle (mark it slow; it may need network).

When done, report: what you implemented, commands I can run to verify it, test results and any failures, a summary of the demo challenge, and the next decision I should make.

**README practice protocol** (keep it short): timebox to the challenge's budget; reproduce the bug before reading code; write a failing test first; use a deliberately limited assistant (plain chat, pasted snippets, a smaller model) rather than an agent with full repo access, to match the interview; talk through your reasoning out loud; fill in diagnosis.md; grade; then reveal and compare with the real fix.

## 12. Session 2 — Practice-challenge authoring (unattended)

It is launched headless from this repo's root, for example:

```bash
mkdir -p ~/.repomentor
claude -p "Do Session 2 as described in CLAUDE.md." \
  --add-dir ~/.repomentor \
  --permission-mode acceptEdits \
  --allowedTools "Bash" \
  > ~/repomentor-session2-summary.txt
```

Nobody is watching and nobody can answer questions. Make reasonable decisions and log them privately.

1. Keep a private log at `$REPOMENTOR_HOME/pack/AUTHORING_LOG.md` with decisions, candidates considered, and rejections with reasons. If the log already exists, resume from it; re-running this session should continue toward the target, not start over.
2. Select 2–3 practice repos per §5, not including the demo repo. Pin and baseline each one.
3. Find candidate fixes. Accept only defects that are behavioral, deterministic, and observable through the public API or CLI; that were fixed in roughly 1–3 source files and 40 or fewer changed source lines; and that require tracing across at least two modules to diagnose. Reject import-time crashes, packaging or dependency issues, Python-version or platform compatibility, locale or encoding quirks, performance, concurrency or timing, docs-only or typing-only changes, and security fixes.
4. Build each challenge per §6 and run `repomentor validate`. Fix the challenge or reject it. Never weaken a validation check to get a challenge through.
5. If you find a harness bug, fix it generically and add a test. Commit messages and code must not reference any practice challenge.
6. Stop at 10 validated challenges or when candidates run out. The minimum goal is 6.

**Final output — the only thing I will read.** A spoiler-free table with: id, source repo name, origin (upstream-fix or synthetic), estimated difficulty, time budget, and validation status. After the table: the number of candidates rejected (no details), any harness changes described generically, and anything I need to do. Nothing else.

## 13. Definition of done

- [ ] The package installs, the `repomentor` CLI runs, and the README explains local use and the practice protocol.
- [ ] The demo challenge passes `validate`, and I understand how it was built.
- [ ] `start` creates a usable workspace with no history, no private files, and a working venv.
- [ ] `grade` evaluates the candidate's copy in a separate directory, verifies it is importing that copy, and distinguishes the untouched defect (FAIL) from the upstream fix (PASS).
- [ ] Grading reports per-criterion results without leaking private tests.
- [ ] `reveal` shows the answer key only when asked.
- [ ] Failure cases produce explicit, actionable errors.
- [ ] Session 2 has produced 6–10 validated practice challenges, and I haven't seen inside any of them.