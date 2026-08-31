---
name: breathing-room
description: Quick, lossy compaction of an in-progress work session's accumulated context — long tool outputs, file dumps, exploratory dead ends, superseded reasoning — into a terse working note that preserves only what's needed to keep going, meaning the current goal, decided facts, state of progress, and next step. Use whenever the user asks to compact, trim, or free up context, says things like "give me some breathing room" or "compact this," or when a session has accumulated a lot of large tool outputs and file contents that are no longer being actively referenced. This is deliberately quick and dirty, not a careful handoff document — some detail loss is expected and acceptable in exchange for speed. A precise, complete handoff to a new session or person is a different, more careful task than this one.
---

# Breathing Room

Fast, lossy context compaction. Trade precision for speed, on purpose.

## Why "quick and dirty" is the point

Sometimes the need is just space to keep working *right now* — not a polished summary someone will read carefully later. A careful handoff document is a different task with different tradeoffs (see "When not to use this" below); over-investing in precision here defeats the purpose. The deal being made is real information loss in exchange for speed, and that's fine as long as it's the *right* information being lost.

## What to keep — don't compress these

- **The current goal/task**, stated plainly, in one line.
- **Decisions already made, and why**, one line each — especially ones that took real back-and-forth to reach. Re-deriving a decision is expensive; restating its conclusion is cheap.
- **Current state**: what's done, what's in progress, what's next.
- **Specific facts that are cheap to lose and expensive to regenerate**: exact file paths touched, exact identifiers/IDs/config values/version numbers, exact error messages still being actively chased, exact user requirements/constraints. Don't paraphrase these — getting one slightly wrong quietly drifts the whole session off course.
- **Anything explicitly flagged as unresolved or blocking.**

## What to cut, aggressively

- **Full contents of files already read** — replace with the file path and a one-line note of what's in it or what changed.
- **Full tool/command output** — keep just the outcome (pass/fail, the key number, the relevant line), not the full stdout/stderr, unless it's an active error being debugged right now.
- **Exploratory dead ends** — approaches tried and abandoned don't need their reasoning preserved. "Tried X, didn't work, moved to Y" is usually enough, and often not even that.
- **Verbose reasoning that already led to a conclusion** — keep the conclusion, drop the trail that got there.
- **Superseded plans** — if the plan changed, keep the current plan, not the old one "for context."
- **Resolved back-and-forth** — once a clarifying exchange is settled, keep only the resolution.

## Process

1. **Skim the accumulated context once, fast.** Don't re-read carefully, don't re-verify anything, don't re-open files to double-check. This step takes seconds — it's a skim, not a re-litigation of the session.
2. **Write the compacted note directly.** No draft-then-revise pass — the first version is the output. Polishing it is wasted effort against the goal.
3. **Say what got dropped, briefly.** One line — "trimmed: 3 full file dumps, 2 failed approaches, verbose debug output" — so the drop is visible without turning into its own itemized report.
4. **Get back to the actual task immediately.** This isn't a stopping point; it's a reset to keep moving.

## Output format

```markdown
## Working state — [task name]

**Goal:** [one line]

**Done:**
- [terse bullet]

**In progress / current step:**
- [terse bullet]

**Next:**
- [terse bullet]

**Key facts (don't lose these):**
- [exact file paths, IDs, values, constraints]

**Dropped:** [one line — roughly what and how much]
```

## When NOT to use this

If what's actually needed is a precise, complete handoff — to a new session, a teammate, or anyone who wasn't following along — that's not this skill. That needs care, not speed, and shouldn't be lossy in the way this deliberately is. If it's unclear which is wanted, say so and confirm the quick-and-dirty tradeoff is acceptable before compacting.

Don't cut anything still actively in play: an error currently being debugged, code not yet committed, exact requirements still governing the work. Quick and dirty means cutting what's already served its purpose — not what's still being used.

## Things to watch for

- **Speed is the point.** If compacting itself turns into a careful, deliberated activity, it has failed at its job.
- **Losing nuance is expected, not a mistake.** That's the trade being made. Flag it once; don't keep apologizing for it.
- **When genuinely unsure whether something is safe to cut, lean toward a one-line mention over dropping it entirely.** A terse mention costs almost nothing; silently losing a real constraint costs a lot more later.
- **This produces a working note for continuing, not a deliverable.** Keep it terse enough to skim in seconds — if it needs careful reading, it's too long for what this is.
