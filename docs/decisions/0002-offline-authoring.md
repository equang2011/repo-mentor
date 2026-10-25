# 0002: Challenge authoring stays offline and curated

- **Status:** accepted
- **Date:** 2026-10-22

## Context

We considered having a web app expose "find repos" and "make challenges" as endpoints. Authoring today is a long agentic run: it clones repos, builds venvs, runs test suites several times, and validates each challenge. Measured cost, at API-equivalent rates for the default coding-agent model, is about **$0.80–0.90 per validated challenge** and roughly 10 minutes of wall time per challenge. Repo gathering is a few dollars per round. Tokens are cheap. Run time, compute, and the quality review a human must do are not.

CLAUDE.md §10 also lists "generating challenges from arbitrary repos at runtime" as a non-goal.

## Decision

Authoring (`/gather-repos`, `/make-challenges`, `repomentor validate`) runs offline, driven by the maintainer and a coding agent. Any future service only *serves* a curated, validated catalog.

## Consequences

- The server stays simple: a catalog, bundles and results, with no job queue for authoring.
- The rate of new challenges is limited by maintainer time, which matters once matches start using challenges up.

## Revisit when

Matches use up challenges faster than offline runs can replace them.
