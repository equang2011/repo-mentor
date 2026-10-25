# Idea: RepoMentor as a practice platform

_Status: exploratory, not approved. Captured 2026-10-22._

## Vision

RepoMentor would be a debugging module on a coding-practice site, alongside data-structures-and-algorithms practice. Sessions are timed (about 40 minutes): you get a realistic repo and a bug ticket, fix it in your own editor, and submit. Later, two people would take the same challenge at the same time, and each gets an LLM-written learning debrief afterward. The goal is to make interview prep and skill-building fun.

## Shape: local-first, thin server

```text
 user's machine                                   server (later)
┌───────────────────────────────┐   bundle   ┌────────────────────────────┐
│ repomentor CLI                │◄──────────│ catalog of validated       │
│  start → workspace + venv     │            │ challenges (public parts)  │
│  ask   → bounded assistant ───┼── proxy ──►│ assistant proxy: limits,   │
│  submit → git diff (patch) ───┼──────────►│ transcripts                │
│ own editor + terminal         │  report    │ grader: apply patch to the │
└───────────────────────────────┘◄──────────│ buggy ref, run private     │
                                             │ tests, store result        │
                                             │ matches: shared clock,     │
                                             │ presence                   │
                                             └────────────────────────────┘
```

### Key mechanics

- **Submit a patch, not files.** The workspace already has one "Initial snapshot" commit, so a submission is `git diff` against it. The server applies the patch to its own pristine copy of the buggy ref and restores the original test files. Uploads are tiny, and users can't swap tests.
- **The server owns the clock.** Store `starts_at` and `ends_at`. Clients only render `ends_at - now`. Reject submissions after `ends_at` plus a short grace period. This removes any timer-syncing problem.
- **Presence is a heartbeat.** The CLI or page pings every ~10 s, and status is `active`, `idle`, `disconnected` or `submitted`. Polling first; WebSockets or server-sent events later as a learning step.
- **The assistant goes through a proxy** (once a second user exists). Limits enforced on the client can be edited away. A server proxy controls the model, delay, context cap and rate limit, and keeps the transcript for the debrief.
- **Private tests never leave the grader** ([decision 0003](../decisions/0003-tests-decide-correctness.md)).

## Proposed stack (for when Stage 3 starts)

- **Backend:** FastAPI, Postgres (Docker Compose locally), SQLAlchemy 2.0 or SQLModel, Alembic migrations.
- **Grading jobs:** a `jobs` table plus one worker process that claims work with `SELECT … FOR UPDATE SKIP LOCKED`. No Celery or Redis at first.
- **Frontend:** Jinja2 templates + HTMX, plus a little Alpine.js for the countdown, plus Tailwind. Keep the JavaScript small enough to read and debug yourself. Consider React only if the match lobby becomes truly interactive.
- **First endpoints:**
  - `GET /challenges`
  - `GET /challenges/{id}/bundle`
  - `POST /sessions`
  - `POST /sessions/{id}/submit`
  - `GET /sessions/{id}/report`
  - later `POST /sessions/{id}/heartbeat`
- **Sandboxing** (required before strangers submit code): run grading in containers with `--network none`, CPU and memory limits, a wall-clock timeout, and a read-only base image.

## Competition and cheating

You can't stop someone from using an outside AI on their own machine.

- Launch with **practice matches** only (friends, invite links, no public ladder), so there's little reason to cheat.
- Make **good use of the bounded assistant** part of the debrief, as it is in interviews that allow AI.
- Ranked play and anomaly signals (for example, a correct fix in 4 minutes with no assistant use) only once there's a community that cares.

## Measured costs (2026-10)

Measured from this project's own Claude Code transcripts, at API-equivalent rates:

| Activity | Cost |
|---|---|
| Authoring | ≈ $0.80–0.90 per validated challenge (≈ 1.5–2 h for 10 challenges) |
| Repo gathering | ≈ $1–2 per round |
| Bounded assistant session | ≈ $0.02–0.03 with a small model (about 20 questions × about 10k tokens of context) |

Conclusion: tokens aren't the constraint. Run time, compute for test suites, and human review of challenge quality are.

## Open questions

- Accounts: GitHub OAuth only?
- Do bundles include each upstream repo's LICENSE? (They must, if we redistribute.)
- How fast do matches use up challenges, compared with how fast we can author them?
- When a challenge is "burned" (answer revealed or widely played), does it move to a free practice tier?
