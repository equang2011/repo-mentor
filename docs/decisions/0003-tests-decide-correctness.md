# 0003: Tests decide correctness; LLMs only give feedback

- **Status:** accepted
- **Date:** 2026-10-22

## Context

The platform idea includes an LLM "scoring" sessions and reporting afterward. LLM judgments aren't deterministic and can be argued with, and in a match someone has to win.

## Decision

1. Pass/fail is decided only by the deterministic grader: per-criterion results from the private tests, plus the existing suite.
2. Ties are broken by time, then by diff size.
3. An LLM may produce a **learning debrief** (investigation approach, how targeted the fix is, how well the assistant was used). It never changes the verdict.
4. Private tests and answer keys never leave the machine that grades. Today that's the user's own machine. Once a second user exists, grading happens on the server from a submitted patch, and users download only the public bundle.

## Consequences

- CLAUDE.md §10 ("no LLM-based grading") still holds. Debriefs need an explicit exception when they're specced.
- A web service can't trust a completion JSON the client sends about itself. It must grade the patch itself.
