---
name: lbotomy
description: Save and restore your working state across opencode sessions — current task, open files, recent decisions, TODOs, and a "where I left off" summary. Use whenever the user says "save state", "checkpoint", "remember where we are", asks to resume/restore a previous session, or starts a session asking "what was I doing" / "where did we leave off". Also trigger at natural session boundaries (before a long pause, when the user says they're stepping away, or when a big task is about to end) to proactively offer a checkpoint.
---

# lbotomy

A memory prosthetic for opencode. opencode sessions don't share context by
default, so this skill gives you a deliberate way to snapshot "what's going
on" at the end of a session and load it back in at the start of the next one.

## State file

State lives in the project root at:

```
.lbotomy/state.json
```

One state file per project. Add `.lbotomy/` to `.gitignore` unless the user
explicitly wants state committed and shared with collaborators (ask if
unclear — some teams like a shared handoff file, most don't).

### Schema

```json
{
  "saved_at": "2026-09-25T14:32:00Z",
  "task": "Short description of the overarching goal/task in progress",
  "status": "in_progress | blocked | ready_for_review | done",
  "summary": "2-5 sentence free-text account of where things stand, written as if briefing someone cold. This is the most important field — prioritize it over the structured ones.",
  "files_touched": [
    {"path": "src/foo.py", "note": "refactored the parser, not yet tested"}
  ],
  "open_todos": [
    "Write tests for the new parser",
    "Fix the edge case with empty input"
  ],
  "recent_decisions": [
    "Chose to use a streaming parser instead of loading the whole file, because inputs can be huge"
  ],
  "blockers": [
    "Waiting on API key from user before integration tests can run"
  ],
  "next_step": "The single most useful next action to take when resuming"
}
```

Only `saved_at`, `task`, and `summary` are required. Omit empty arrays rather
than including them empty.

## Saving state (checkpoint)

Trigger phrases: "save state", "checkpoint", "save my progress", "remember
where we are", or a natural session-ending moment.

1. Look back over the session: what was the goal, what got done, what's
   unfinished, what decisions were made and why, what's the immediate next
   step.
2. Check if `.lbotomy/state.json` already exists.
   - If it exists and this is the *same* task continuing, update it in place
     (overwrite `saved_at`, merge/update the other fields — don't just
     blindly append duplicate TODOs).
   - If it exists but describes a *different, now-finished or abandoned*
     task, replace it, but mention to the user that you're overwriting a
     prior checkpoint and briefly say what it was, in case they still need it.
3. Write the new `.lbotomy/state.json`.
4. Confirm to the user in one or two lines what was saved — don't dump the
   whole JSON back at them unless they ask.

Keep `summary` genuinely useful: write it as a briefing note to a
collaborator who knows the project but not this session, not as a diary
entry.

## Restoring state (resume)

Trigger phrases: "restore state", "resume", "where did we leave off",
"what was I doing", or the start of a session where the user seems to expect
continuity.

1. Read `.lbotomy/state.json`. If it doesn't exist, say so plainly — don't
   fabricate a prior state.
2. If it exists, briefly summarize it back to the user in prose (lead with
   `summary` and `next_step`; mention `blockers` if any exist) rather than
   printing raw JSON.
3. If `status` is `blocked`, surface the blocker prominently before
   suggesting next steps.
4. Ask or confirm whether to proceed with `next_step`, rather than just
   diving in — the codebase may have changed since the checkpoint was saved.

## Notes

- This skill does not run automatically in the background — it only acts
  when invoked via the trigger phrases above, or when explicitly offered and
  accepted by the user at a natural boundary.
- If `.lbotomy/state.json` is malformed or unreadable, say so and ask the
  user whether to start fresh rather than silently discarding it.
- Multiple concurrent tasks: if the user is clearly juggling more than one
  independent thread of work, offer to use `.lbotomy/state.<slug>.json`
  instead of a single file, and ask what slug to use.
