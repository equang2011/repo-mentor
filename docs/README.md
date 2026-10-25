# RepoMentor docs

Planning and design docs live here, versioned next to the code they describe.

| Folder | What goes in it | Status |
|---|---|---|
| [`roadmap.md`](roadmap.md) | Stages, the current focus, and the gate for moving to the next stage | Living document |
| [`specs/`](specs/) | One buildable spec per feature, numbered (`001-…`) | **Approved** specs are what gets built |
| [`decisions/`](decisions/) | Short decision records: what we decided, why, and when to revisit | Settled, and changed only by a new record |
| [`ideas/`](ideas/) | Exploratory thinking that hasn't been approved | Not a commitment |

## Lifecycle

1. An idea starts in `ideas/`.
2. When it's worth building, it becomes a spec in `specs/` with status `draft`.
3. After review it becomes `approved`, and only then does code get written.
4. Any lasting choice made along the way gets a record in `decisions/`.
5. When a spec ships, its status becomes `done`, and the roadmap is updated.

## Rules for these docs

- **Spoiler rules (CLAUDE.md §3) apply here too.** Never describe a practice challenge's defect, fix, or private tests, and never name a practice repo. The demo challenge (`demo-001`, mistune) is fine to discuss.
- **CLAUDE.md stays the standing brief.** These docs refine it for specific features. If a spec conflicts with CLAUDE.md, CLAUDE.md wins until it's updated.
- **Write specs so someone else could build from them.** That includes you in a month, or another AI assistant helping you.
