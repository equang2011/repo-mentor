# 0001: Local-first; no browser IDE

- **Status:** accepted
- **Date:** 2026-10-22

## Context

The practice we care about is debugging in a real editor and terminal: reproducing the bug, running tests, adding prints, reading code. A browser IDE seems to offer zero-setup sessions and identical environments for matches. But the editor is the easy part. The hard part is giving every user a place to *run* code: a container per session, startup and shutdown, routing, resource limits, abuse prevention, and the cost of all that.

Rough effort, for a first web app worked on part-time:

| Option | Effort |
|---|---|
| "Open in Codespaces" button (GitHub hosts the environment) | days |
| Editor in the browser, with tests run on the server | 1–3 weeks |
| Python running in the browser (Pyodide) | weeks of experimenting; some repos won't work (no `subprocess`, no real git) |
| Full cloud IDE (code-server, or an editor plus a terminal in a container per session) | 1–3 months, then ongoing operations |

## Decision

Users work locally in their own editor and terminal. RepoMentor provides the challenge, the clock, the submission path and the grade. Any web app we build serves those, not an editor.

## Consequences

- Setup friction (venvs, platform quirks) stays our problem. `repomentor start` must keep producing a working environment with one command.
- Matches can't watch keystrokes, so anti-cheating is limited. See [`../ideas/platform.md`](../ideas/platform.md).
- Cheap escape hatch: add a `devcontainer.json` to bundles so users can open them in GitHub Codespaces.

## Revisit when

Setup failures are the top reason users drop off, or ranked play needs a controlled environment. If that happens, try Pyodide as a weekend experiment before considering a full cloud IDE.
