---
description: Rigorously grade a completed practice challenge against its hidden key
argument-hint: "[challenge folder; defaults to the most recent in ./challenges]"
---

Grade the challenge at: $ARGUMENTS (if empty, use the most recently modified folder in `./challenges/`).

You are a strict, fair senior reviewer. Grade only against what the README actually specified. Do not penalize the candidate for requirements that were never stated, and do give credit for a reasonable stated assumption on a deliberately open point.

## Steps
1. Read `README.md`, `SUBMISSION.md`, `task1_implement/solution.py` and everything in `.grader/`.
2. **Task 1:** run `.grader/hidden_tests.py` against the candidate's `solution.py`. Report pass/fail per test. For each failure, give the input, the expected and actual output, and the root cause in the candidate's code. Assess readability, naming, structure, error handling and time/space complexity against the stated constraints.
3. **Task 2:** compare the candidate's findings to `review_key.md`. Each planted bug is found and correctly explained, found but poorly explained, or missed. Flag false positives, including flagging the decoy as a bug, and check whether the proposed fixes are actually correct by applying them and running the relevant tests.
4. **Task 3:** compare the candidate's verdict and reasoning to `compare_key.md`. Reward specific, verifiable arguments. Penalize vague claims ("B is cleaner"), arguments based on length, and missed correctness issues.
5. **Communication:** were the explanations in full sentences, specific and free of filler? Did the candidate address every requirement and respect the scope and format?

## Output
Write `GRADE.md` in the challenge folder containing:
- Score out of 100, broken down by the rubric lines.
- Specific mistakes, each with file:line or quoted text, why it's wrong and what would have earned full marks.
- The 2–3 habits to fix before the real assessment, ranked by how many points they cost.
- Only after all of the above: the reference solution and full answer key, so the candidate can study them.

In chat, give only the total score, the breakdown and the top habits to fix, then point to `GRADE.md`.
