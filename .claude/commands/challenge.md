---
description: Generate a timed practice coding assessment (implement + review + compare) in a new folder
argument-hint: "[language=python] [minutes=35] [difficulty=medium] [mode=exam|learn] [focus, e.g. 'data processing']"
---

You are a senior engineer designing a realistic practice assessment modeled on paid AI-coding evaluation platforms. These assessments reward careful reasoning, verified behavior and clear written explanation, not LeetCode tricks.

Arguments: $ARGUMENTS
Defaults when missing: language = Python (standard library only), minutes = 35, difficulty = medium, mode = exam, focus = your choice of realistic business logic.

- **difficulty:** `easy`, `medium` or `hard`. It scales the size limits in section 2.
- **mode:** `exam` is a timed simulation. `learn` is untimed and splits Task 1 into stages with checkpoint tests, for use with `/coach`.

## 0. Avoid repeats
List `./challenges/`. Skim each existing `README.md` and choose a scenario, domain and bug type that differ from previous challenges.

## 1. Create the folder
`./challenges/<YYYY-MM-DD>-<short-slug>/` containing:

```
README.md            # scenario, rules, time limit, the three tasks, submission instructions
SUBMISSION.md        # template the candidate fills in (sections per task)
task1_implement/
  solution.py        # starter: signatures, docstrings, `raise NotImplementedError` — no logic
  test_examples.py   # ONLY the 3 illustrative examples from the README, as runnable tests
  test_checkpoints.py  # learn mode only: one small test class per stage (see section 2)
task2_review/
  prompt.md          # the original request the "submitted" code was meant to satisfy
  submitted.py       # a plausible, clean-looking solution with planted defects
task3_compare/
  prompt.md          # a short coding question
  response_a.md      # two candidate answers (code + explanation)
  response_b.md
.grader/             # answer key — the candidate must not open this
  reference_solution.py
  hidden_tests.py    # thorough tests for task 1 AND tests that expose each task-2 bug
  review_key.md      # each planted bug: location, why it is wrong, failing input, fix; plus non-bugs that look suspicious
  compare_key.md     # which response is better and why, per dimension
  rubric.md          # point allocation (see section 4)
```

## 2. Task design rules
**Overall:** sized so a competent intermediate developer finishes all three tasks in the time limit, with the implementation taking about half of it. Use a realistic scenario (orders, scheduling, logs, inventory, billing, rate limiting, etc.) and the standard library only.

**Task 1 (Implement):** state precise input/output specs, explicit constraints and size bounds, required error behavior, and exactly 3 illustrative examples. Require real reasoning: ordering rules, ties, boundary inclusivity, malformed input, or a complexity requirement that rules out the naive approach. Do not reveal the algorithm. Never leave anything ambiguous by accident. If something is deliberately left to the candidate's judgment, say so and require them to state their assumption.

Open Task 1 with a two- or three-sentence plain-language summary of what the function does, before the detailed rules.

**Task 1 size limits.** A spec that is too big turns the exercise into typing practice. For a 35-minute challenge at each difficulty:

| | easy | medium | hard |
|---|---|---|---|
| Distinct rules (each computation, tie-break, threshold or ordering rule counts as one) | ≤ 5 | ≤ 8 | ≤ 11 |
| Required error cases | ≤ 3 | ≤ 5 | ≤ 7 |
| Reference solution, excluding docstrings and blank lines | ≤ 30 lines | ≤ 45 lines | ≤ 65 lines |
| Spec length, excluding examples | ≤ 250 words | ≤ 400 words | ≤ 550 words |

Scale the limits in proportion to the time limit. Pick a few meaningful error cases rather than requiring full schema validation of every field, unless the focus asks for validation.

**Learn mode only:** split Task 1 into three or four stages that build on each other (for example: validate and normalize input; core computation; selection and tie-breaking; output). List them in the README after the spec. In `test_checkpoints.py`, write one small test class per stage that passes once that stage is done. These tests may only check behavior the spec states, and must not reveal anything beyond it.

**Task 2 (Review):** `submitted.py` should pass the obvious cases and look professional. Plant 2–4 defects of different kinds (for example an off-by-one or inclusive/exclusive boundary, mutation of an input or a shared default, wrong behavior on empty or duplicate input, swallowed exceptions, a hidden O(n²) where the constraints demand better, or an unstated assumption the spec doesn't grant). Include at least one thing that looks wrong but is actually fine. The candidate must identify each issue, explain why it fails with a concrete input, and propose a fix.

**Task 3 (Compare):** two responses to the same prompt, where neither is perfect and the better one is not the longer or more confident one. They should differ on correctness, edge cases, complexity and explanation quality. The candidate picks one and writes a justified comparison in full sentences.

## 3. Verify before finishing (required)
- `reference_solution.py` passes 100% of the task 1 hidden tests.
- The starter `solution.py` fails them, but `test_examples.py` is importable and collects correctly.
- Every planted bug in `submitted.py` causes at least one specific hidden test to fail. Record which test in `review_key.md`.
- The hidden tests cover boundaries, empty input, duplicates/ties, invalid input and one larger input that enforces the complexity constraint.
- Re-read the README against the reference solution. Every behavior the tests check must be stated or clearly implied by the spec. If it isn't, fix the spec or drop the test.
- **Size check.** Count Task 1's rules, error cases, spec words and reference-solution lines, and confirm each is within the section 2 limits. If any is over, cut the spec and regenerate the affected files; don't just note it.
- **Blind solve.** Give a second subagent only the README and the starter `solution.py`, with no access to `.grader/`, and have it implement Task 1 and run the hidden tests. Any test it fails because the spec was unclear or contradictory means the spec needs fixing. If its solution exceeds the line limit by more than half, the task is too big.

Run these checks with `python -m pytest`, using unittest if pytest is unavailable.

## 4. Rubric (write to `.grader/rubric.md`)
Out of 100: Task 1 correctness on hidden tests 35, Task 1 code quality and complexity 10, Task 2 bugs found and explained 25 (false positives cost points), Task 3 judgment and justification 20, communication and requirement adherence across all written answers 10.

## 5. Keep the answer key out of sight
Use a subagent (the Agent tool) to write and verify everything in `.grader/`, so its contents don't appear in this transcript. Never print reference code, hidden tests, bug locations or the compare verdict in your messages.

## 6. Final message
Only: the folder path, the mode, and one line of instructions. No hints, no summary of the tasks.

- **exam:** the time limit, then "Start a timer, read README.md, write answers in SUBMISSION.md and task1_implement/solution.py, then run /grade <folder>."
- **learn:** "Untimed. Run /coach <folder> to work through it stage by stage, then /grade <folder>."
