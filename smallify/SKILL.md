---
name: smallify
description: Break down a ticket, task, or feature request into an extremely explicit, granular, step-by-step implementation plan suitable for execution by a small, local, or otherwise weaker LLM with limited reasoning and context. Use this whenever the user asks to "smallify" a ticket, wants a task "dumbed down" or "spelled out," is prepping work for a local/open-source/lightweight coding model, or asks for maximally explicit steps that name exact files, functions, and code changes for an implementation task.
---

# Smallify

Turn a ticket into a plan a small model can execute without having to think.

## Why this matters

Small and local LLMs don't have the reasoning capacity to fill in gaps, infer intent from vague language, hold a multi-step plan in working memory, or safely explore a codebase to find "the right place" for a change. They do well when told exactly: open this file, find this exact text, replace it with this exact text, run this exact command, check for this exact result.

Every ambiguity left in a ticket becomes a failure point for a small model. The job of this skill is to do all the exploration, decision-making, and disambiguation up front — in this conversation, with a capable model — so the small model's job becomes close to mechanical execution.

This applies regardless of language or stack. The patterns below (precise pointers, exact file paths, exact commands) work the same whether the codebase is TypeScript, Python, Go, Rust, Java, C++, or anything else — adapt the verification commands to whatever the project actually uses, but keep the same level of explicitness.

This skill only produces the plan. It doesn't touch the codebase — no code gets written or changed here. The one file it does modify is the ticket itself.

## Process

### 1. Understand the ticket
Read it fully. Identify the goal, the definition of done, and any explicit constraints. Read any linked context that's available (docs, prior discussion, related tickets).

Check for existing ticket metadata — a YAML front matter block, or key-value fields like `Status:`, `Priority:`, `Assignee:`, `Blocked by:`, `Labels:`, `Sprint:`, `Due:`, ticket IDs, links to related tickets, and so on. Note every such field verbatim; you'll carry it forward untouched in step 8. Don't infer or invent fields the ticket doesn't have.

### 2. Investigate the codebase before writing anything
This is the most important step — don't skip or approximate it.
- Search for and open every file the ticket touches, even implicitly.
- Read the *actual current code*, not remembered or assumed code — exact function signatures, imports, naming conventions, nearby style.
- Identify every file that needs to change. Don't leave "find the right place" as a task for the small model — that's your job now.

### 3. Resolve ambiguity yourself
If the ticket is underspecified in a way that affects implementation (e.g. "add validation" without saying what's valid), pick a reasonable interpretation and state it plainly at the top of the plan. Ask the user one clarifying question only if the choice meaningfully changes the design. Never let an ambiguous instruction pass through to the small model — it will guess, and guess wrong.

### 4. Decompose into atomic steps
- One step = one coherent, independently verifiable change. If a step's description contains "and," consider splitting it.
- Order steps by dependency (define a type before using it, add a migration before code that queries the new column, etc).
- Each step must be self-contained: don't assume the small model remembers *why* earlier steps happened, only their file-system effects.

### 5. Point to exactly what needs to change — without writing the code
Every step should name a location so precisely that there's no exploration or invention involved, but describe the *change*, not the implementation:
- **Create** — full path, plus a precise description of the file's purpose: what it should export/contain, what it depends on, roughly how it fits into the surrounding code. Not the file's contents.
- **Modify** — full path, plus an exact anchor (function/class name, line range, or "directly above/below X") locating the spot, and a plain-language description of the required behavior change.
- **Delete** — full path, plus a check (or a prior step) confirming nothing else still imports or references it.
- **Rename/move** — treat as create + delete pointers, and list every other file that imports the old path.

The description should be specific enough that a small model reading it has only one reasonable way to implement it — no design decisions left open — while leaving the actual code to be written at execution time.

### 6. Give every step a verification action
Small models don't reliably self-check. Attach to each step (or small cluster of steps):
- An exact command to run (`npm test path/to/file.test.ts`, `pytest tests/test_x.py::test_y`)
- What "pass" looks like (exit code 0, a specific assertion, no new lint errors)

If the ticket has no tests, decide where a test belongs and write its exact content as its own step.

### 7. Close with an overall acceptance check
End with a final step tied to the ticket's definition of done — e.g. "run the full test suite" or "start the app and confirm X happens."

### 8. Carry forward the ticket's own metadata, unchanged
If the original ticket had a metadata block (YAML front matter, or fields like `Status:`, `Priority:`, `Assignee:`, `Blocked by:`, `Labels:`, `Sprint:`, ticket ID, etc.), reproduce it at the top of the rewritten ticket exactly as it was — same fields, same values. This is tracking data owned by whatever system the ticket lives in; smallify's job is to make the *body* explicit, not to touch, reinterpret, or invent tracking fields. If the ticket had no metadata, don't add any.

## Output format

Rewrite the ticket itself into this structure — this is the only file that changes.

```markdown
---
[Any metadata fields the original ticket had — status, priority, assignee, blockers,
labels, ticket id, etc. — reproduced exactly. Omit this whole block if the ticket had none.]
---

# [Ticket title]

## Goal
[1-2 sentence restatement of what "done" means]

## Assumptions
[Any interpretation calls you made, stated plainly. Omit if none.]

## Files touched
- CREATE: path/to/new_file.ts
- MODIFY: path/to/existing_file.ts
- DELETE: path/to/old_file.ts

## Steps

### Step 1: [short imperative title]
**File:** `path/to/file` (create | modify | delete)
[If modify: exact anchor (function/class/section) + plain description of the required change]
[If create: description of the file's purpose and what it should contain]
**Verify:** [exact command + expected result]

### Step 2: ...

## Final check
[command(s) confirming the whole ticket is done]
```

## Example: good vs. bad step

**Good — precise pointer, no code, works in any language:**

    **File:** `src/api/users.ts` (modify)
    Anchor: the `getUser` function.
    Change: after the existing lookup call, check whether the result is null/undefined. If so, throw a `NotFoundError` whose message includes the requested id. Otherwise return the user as before, unchanged.
    **Verify:** `npm test src/api/users.test.ts` — the new "throws NotFoundError for missing user" test passes.

    ---

    **File:** `api/users.py` (modify)
    Anchor: the `get_user` function.
    Change: after the existing lookup, check whether the result is `None`. If so, raise `NotFoundError` with a message that includes the user id. Otherwise return the user unchanged.
    **Verify:** `pytest tests/test_users.py::test_get_user_raises_when_missing` passes.

**Bad — too vague, leaves a design decision open:**

    Update the user fetching logic to handle missing users.

**Also bad — too much, does the small model's job for it:**

    Replace the function body with:
    ```ts
    export function getUser(id: string) {
      const user = db.users.find(id);
      if (!user) throw new NotFoundError(`User ${id} not found`);
      return user;
    }
    ```

The commands you attach as verification should match the project's own ecosystem — `go test ./...`, `cargo test`, `mvn test`, `pytest`, `npm test`, whatever the repo actually uses. Check the repo (build files, CI config, README) rather than assuming.

## Things to watch for

- **Preserve ticket metadata, don't reinterpret it.** Whatever status/priority/blocker/assignee fields the original ticket had, copy them forward as-is. Don't mark something "blocked" or change its status based on your own read of the work — that's not smallify's call to make.
- **Don't invent tracking fields.** If the ticket had no metadata block, the rewritten ticket gets none either.
- **Describe the change, don't write it.** Name the exact file and anchor, and state the required behavior precisely enough that only one implementation is reasonable — but leave the actual code to the model executing the plan.
- **Don't touch the codebase.** This skill only produces the plan; the ticket is the only file it edits.
- **Don't let steps balloon.** More than one change, or more than one file, means split the step.
- **Name exact identifiers.** Function names, variables, file paths, config keys — never "the config file" or "the relevant handler."
- **State non-obvious ordering explicitly** ("must run after Step 3 because it imports the type added there").
- **Don't assume the small model can search well.** Give it the exact search string or location instead of "find where X happens."
- **Use exact commands, not descriptions of commands** — `npm run test:unit` or `go test ./...` or `mvn -q test`, not "run the tests."
- **Watch for scope creep.** If investigating the codebase reveals the ticket is bigger than it reads, say so up front rather than silently producing a sprawling plan — flag it to the user before smallifying the whole thing.
### 3. Resolve ambiguity yourself
If the ticket is underspecified in a way that affects implementation (e.g. "add validation" without saying what's valid), pick a reasonable interpretation and state it plainly at the top of the plan. Ask the user one clarifying question only if the choice meaningfully changes the design. Never let an ambiguous instruction pass through to the small model — it will guess, and guess wrong.

### 4. Decompose into atomic steps
- One step = one coherent, independently verifiable change. If a step's description contains "and," consider splitting it.
- Order steps by dependency (define a type before using it, add a migration before code that queries the new column, etc).
- Each step must be self-contained: don't assume the small model remembers *why* earlier steps happened, only their file-system effects.

### 5. Point to exactly what needs to change — without writing the code
Every step should name a location so precisely that there's no exploration or invention involved, but describe the *change*, not the implementation:
- **Create** — full path, plus a precise description of the file's purpose: what it should export/contain, what it depends on, roughly how it fits into the surrounding code. Not the file's contents.
- **Modify** — full path, plus an exact anchor (function/class name, line range, or "directly above/below X") locating the spot, and a plain-language description of the required behavior change.
- **Delete** — full path, plus a check (or a prior step) confirming nothing else still imports or references it.
- **Rename/move** — treat as create + delete pointers, and list every other file that imports the old path.

The description should be specific enough that a small model reading it has only one reasonable way to implement it — no design decisions left open — while leaving the actual code to be written at execution time.

### 6. Give every step a verification action
Small models don't reliably self-check. Attach to each step (or small cluster of steps):
- An exact command to run (`npm test path/to/file.test.ts`, `pytest tests/test_x.py::test_y`)
- What "pass" looks like (exit code 0, a specific assertion, no new lint errors)

If the ticket has no tests, decide where a test belongs and write its exact content as its own step.

### 7. Close with an overall acceptance check
End with a final step tied to the ticket's definition of done — e.g. "run the full test suite" or "start the app and confirm X happens."

## Output format

Rewrite the ticket itself into this structure — this is the only file that changes.

```markdown
# [Ticket title]

## Goal
[1-2 sentence restatement of what "done" means]

## Assumptions
[Any interpretation calls you made, stated plainly. Omit if none.]

## Files touched
- CREATE: path/to/new_file.ts
- MODIFY: path/to/existing_file.ts
- DELETE: path/to/old_file.ts

## Steps

### Step 1: [short imperative title]
**File:** `path/to/file` (create | modify | delete)
[If modify: exact anchor (function/class/section) + plain description of the required change]
[If create: description of the file's purpose and what it should contain]
**Verify:** [exact command + expected result]

### Step 2: ...

## Final check
[command(s) confirming the whole ticket is done]
```

## Example: good vs. bad step

**Good — precise pointer, no code, works in any language:**

    **File:** `src/api/users.ts` (modify)
    Anchor: the `getUser` function.
    Change: after the existing lookup call, check whether the result is null/undefined. If so, throw a `NotFoundError` whose message includes the requested id. Otherwise return the user as before, unchanged.
    **Verify:** `npm test src/api/users.test.ts` — the new "throws NotFoundError for missing user" test passes.

    ---

    **File:** `api/users.py` (modify)
    Anchor: the `get_user` function.
    Change: after the existing lookup, check whether the result is `None`. If so, raise `NotFoundError` with a message that includes the user id. Otherwise return the user unchanged.
    **Verify:** `pytest tests/test_users.py::test_get_user_raises_when_missing` passes.

**Bad — too vague, leaves a design decision open:**

    Update the user fetching logic to handle missing users.

**Also bad — too much, does the small model's job for it:**

    Replace the function body with:
    ```ts
    export function getUser(id: string) {
      const user = db.users.find(id);
      if (!user) throw new NotFoundError(`User ${id} not found`);
      return user;
    }
    ```

The commands you attach as verification should match the project's own ecosystem — `go test ./...`, `cargo test`, `mvn test`, `pytest`, `npm test`, whatever the repo actually uses. Check the repo (build files, CI config, README) rather than assuming.

## Things to watch for

- **Describe the change, don't write it.** Name the exact file and anchor, and state the required behavior precisely enough that only one implementation is reasonable — but leave the actual code to the model executing the plan.
- **Don't touch the codebase.** This skill only produces the plan; the ticket is the only file it edits.
- **Don't let steps balloon.** More than one change, or more than one file, means split the step.
- **Name exact identifiers.** Function names, variables, file paths, config keys — never "the config file" or "the relevant handler."
- **State non-obvious ordering explicitly** ("must run after Step 3 because it imports the type added there").
- **Don't assume the small model can search well.** Give it the exact search string or location instead of "find where X happens."
- **Use exact commands, not descriptions of commands** — `npm run test:unit` or `go test ./...` or `mvn -q test`, not "run the tests."
- **Watch for scope creep.** If investigating the codebase reveals the ticket is bigger than it reads, say so up front rather than silently producing a sprawling plan — flag it to the user before smallifying the whole thing.
### 4. Decompose into atomic steps
- One step = one coherent, independently verifiable change. If a step's description contains "and," consider splitting it.
- Order steps by dependency (define a type before using it, add a migration before code that queries the new column, etc).
- Each step must be self-contained: don't assume the small model remembers *why* earlier steps happened, only their file-system effects.

### 5. Make every file operation explicit
For each step, state per file:
- **Create** — full path, and the complete initial contents.
- **Modify** — full path, plus an unambiguous anchor: the exact existing code to find (verbatim, copy-pasteable) and exactly what to replace it with. Never say "update the relevant function" — name it.
- **Delete** — full path, plus a check (or a prior step) confirming nothing else still imports or references it.
- **Rename/move** — treat as create + delete, and list every other file that imports the old path.

### 6. Give every step a verification action
Small models don't reliably self-check. Attach to each step (or small cluster of steps):
- An exact command to run (`npm test path/to/file.test.ts`, `pytest tests/test_x.py::test_y`)
- What "pass" looks like (exit code 0, a specific assertion, no new lint errors)

If the ticket has no tests, decide where a test belongs and write its exact content as its own step.

### 7. Close with an overall acceptance check
End with a final step tied to the ticket's definition of done — e.g. "run the full test suite" or "start the app and confirm X happens."

## Output format

The original ticket file is modified.

```markdown
# [Ticket title]

**What to build:** [what is being built by the ticket]

**Blocked by:** [blocker ticket number] ([blocker ticket title).

**Status:** [done, ready-for-agent, superseded, etc.]

## Goal
[1-2 sentence restatement of what "done" means]

## Assumptions
[Any interpretation calls you made, stated plainly. Omit if none.]

## Files touched
- CREATE: path/to/new_file.ts
- MODIFY: path/to/existing_file.ts
- DELETE: path/to/old_file.ts

## Steps

### Step 1: [short imperative title]
**File:** `path/to/file.ts` (create | modify | delete)
[If modify: exact old code block → exact new code block]
[If create: full file contents]
**Verify:** [exact command + expected result]

### Step 2: ...

## Final check
[command(s) confirming the whole ticket is done]

Smallified on [date and time]
```

## Example: good vs. bad step

**Good — concrete and copy-pasteable, in any language:**

    **File:** `src/api/users.ts` (modify)
    Find:
    ```ts
    export function getUser(id: string) {
      return db.users.find(id);
    }
    ```
    Replace with:
    ```ts
    export function getUser(id: string) {
      const user = db.users.find(id);
      if (!user) throw new NotFoundError(`User ${id} not found`);
      return user;
    }
    ```
    **Verify:** `npm test src/api/users.test.ts` — the new "throws NotFoundError for missing user" test passes.

    ---

    **File:** `api/users.py` (modify)
    Find:
    ```python
    def get_user(user_id: str):
        return db.users.find(user_id)
    ```
    Replace with:
    ```python
    def get_user(user_id: str):
        user = db.users.find(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user
    ```
    **Verify:** `pytest tests/test_users.py::test_get_user_raises_when_missing` passes.

**Bad — too vague for a small model, in any language:**

    Update the user fetching logic to handle missing users.

The commands you attach as verification should match the project's own ecosystem — `go test ./...`, `cargo test`, `mvn test`, `pytest`, `npm test`, whatever the repo actually uses. Check the repo (build files, CI config, README) rather than assuming.

## Things to watch for

- **Don't modify anything but the ticket.** No code or other files should be touched.
- **Don't let steps balloon.** More than one find/replace pair, or more than one file, means split the step.
- **Name exact identifiers.** Function names, variables, file paths, config keys — never "the config file" or "the relevant handler."
- **State non-obvious ordering explicitly** ("must run after Step 3 because it imports the type added there").
- **Don't assume the small model can search well.** Give it the exact search string or location instead of "find where X happens."
- **Use exact commands, not descriptions of commands** — `npm run test:unit` or `go test ./...` or `mvn -q test`, not "run the tests."
- **Match the language's own idioms.** Don't force a step's code onto a pattern from a different ecosystem (e.g. don't write Python error handling like it's JavaScript). Base every snippet on the actual surrounding code you read in step 2.
- **Watch for scope creep.** If investigating the codebase reveals the ticket is bigger than it reads, say so up front rather than silently producing a sprawling plan — flag it to the user before smallifying the whole thing.
