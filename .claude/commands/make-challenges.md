---
description: Launch Session 2 in replenish mode headless; you see only the spoiler-free summary
allowed-tools: Bash
---

Launch the headless authoring run. Do not do any authoring in this session, and do not read anything in the pack.

1. Pick the summary path `~/repomentor-replenish-<YYYY-MM-DD-HHMM>-summary.txt` using the current local time.
2. From the repo root, run this with the Bash tool and `run_in_background: true`:

   ```bash
   mkdir -p ~/.repomentor && claude -p "Do Session 2 in replenish mode as described in CLAUDE.md." \
     --add-dir ~/.repomentor \
     --permission-mode acceptEdits \
     --allowedTools "Bash" \
     > <summary path> 2>&1
   ```

3. Tell me the summary path and that the run takes a while. Then stop.
4. When the background job finishes, say only that it finished and its exit code. Do not read or summarize the summary file; I'll read it myself.
