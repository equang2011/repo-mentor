# Roadmap

_Last updated: 2026-10-22_

RepoMentor started as a tool for one person to prepare for a debugging interview. That interview was cancelled, and RepoMentor is now a longer-term product project and a vehicle for learning. The long-term idea is a debugging module for a coding-practice platform with timed sessions and, eventually, peer matches. See [`ideas/platform.md`](ideas/platform.md).

The strategy is to **stay local-first and add a server only when a second person needs one** ([decision 0001](decisions/0001-local-first.md)).

## Stage 0: Harness (done)

- `list`, `start`, `grade`, `reveal` and `validate`, with the demo challenge and an authored practice pack.
- Authoring and repo gathering run as offline sessions driven by a coding agent (CLAUDE.md §12 and §14).

## Stage 1: Bounded assistant CLI (current)

- Spec: [`specs/001-assistant-cli.md`](specs/001-assistant-cli.md)
- `repomentor ask <session>`: a deliberately limited AI helper that can't see the repo, with saved transcripts and a usage line in the grade report.
- **Done when:** the spec's acceptance criteria pass, and you've used it in at least two real practice sessions.

## Stage 2: Local practice loop polish (next, small)

Candidates, each about 1–2 hours and standard library only:

- `repomentor stats`: attempts, pass rate, and time against budget, by difficulty and over time.
- Timed mode: `start --timed` shows the deadline, and `grade` flags overtime.
- Debrief prompts after `grade`: interviewer-style questions to answer out loud or in `diagnosis.md`.

**Gate to Stage 3:** someone other than you wants to use RepoMentor, or you need results across machines.

## Stage 3: Thin web service (only once a second user exists)

- FastAPI + Postgres. Challenge catalog, public bundle download, sessions whose clock the server owns, **patch submission with server-side grading**, and results history.
- **Grading must move to the server here.** Private tests can't ship to users' machines ([decision 0003](decisions/0003-tests-decide-correctness.md)).
- Frontend: server-rendered templates + HTMX. No browser IDE ([decision 0001](decisions/0001-local-first.md)).
- Write a spec before starting. Sketch: [`ideas/platform.md`](ideas/platform.md).

## Stage 4: Matches (later)

- Invite link, a shared timer controlled by the server, presence (active, idle, disconnected, submitted), and side-by-side results.
- **Needs sandboxed grading** (containers with no network), because it runs other people's code.

## Always on

- Authoring stays offline and curated ([decision 0002](decisions/0002-offline-authoring.md)). Keep the pack replenished with `/gather-repos` and `/make-challenges`.
