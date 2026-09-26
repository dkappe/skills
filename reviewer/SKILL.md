---
name: reviewer
description: Evaluates work on a specific ticket, scores it from 1-10, saves the output to a specified markdown file, and updates the ticket's status to Done if it passes or Open if it fails.
---

# Ticket Reviewer

Evaluate the work implemented for a given ticket and write the complete review to the specified markdown destination.

## Argument Parsing
The user invokes this skill using the pattern:
`/reviewer ticket <ticket_id> write to <target_file.md>`

1. Extract `<ticket_id>` (e.g., `01`, `PROJ-123`).
2. Extract `<target_file.md>` (e.g., `review1.md`, `reviews/review1.md`).

## Workflow

1. **Locate Ticket & Changes:**
   - Tickets live in `docs/issues`. Read the ticket file for `<ticket_id>` from there (e.g. `docs/issues/<ticket_id>.md`). If the file doesn't exist, search `docs/issues` for the ID in a filename or front matter (`id:`/`ticket:` field).
   - If no ticket file is found — or more than one matches `<ticket_id>` — stop and ask the user instead of guessing. Do not write any review or status update.
   - Identify and read all source files created or modified for this ticket.

2. **Evaluate Quality:**
   - Assess correctness, edge cases, error handling, clean architecture, and project idioms.
   - Rate the implementation from **1.0 to 10.0**.
   - If the score is **greater than 8.5**, mark the verdict as **PASSING**.
   - If the score is **8.5 or lower**, mark the verdict as **NEEDS WORK**.

3. **Update Ticket Status:**
   - Locate the ticket file for `<ticket_id>` in `docs/issues` (the same file read in step 1). Never update a status anywhere else.
   - If the verdict is **PASSING**, set the ticket's status to **Done**.
   - If the verdict is **NEEDS WORK**, set the ticket's status to **Open**.
   - Update only the status field; leave all other ticket metadata and content untouched. Match the ticket file's existing status format (e.g., `Status: Done`, `- [ ]`/`- [x]` checkbox). If the ticket has no status field, add one.

4. **Write Review to File:**
   Use the file-writing tool to write the evaluation directly to `<target_file.md>` matching this format:

   ```markdown
   # Code Review: Ticket <ticket_id>

   - **Status:** PASSING / NEEDS WORK
   - **Score:** [X.X] / 10.0 (Passing threshold: > 8.5)
   - **Ticket Status:** Set to Done / Set to Open

   ## Summary
   [1-2 sentences on implementation readiness and overall quality]

   ## Strengths
   - [What was implemented cleanly]

   ## Deficiencies & Edge Cases
   - [Bugs, missing validations, or unhandled conditions]

   ## Concrete Improvements
   1. **[Priority]**: [Actionable fix with brief code snippet if helpful]
   2. **[Improvement]**: [Refactor or cleanup recommendation]
   
