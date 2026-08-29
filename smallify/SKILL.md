---
name: smallify
description: Break down a ticket, task, or feature request into an extremely explicit, granular, step-by-step implementation plan suitable for execution by a small, local, or otherwise weaker LLM with limited reasoning and context. Use this whenever the user asks to "smallify" a ticket, wants a task "dumbed down" or "spelled out," is prepping work for a local/open-source/lightweight coding model, or asks for maximally explicit steps that name exact files, functions, and code changes for an implementation task.
---

# Smallify

Turn a ticket into a plan a small model can execute without having to think.

## Why this matters

Small and local LLMs don't have the reasoning capacity to fill in gaps, infer intent from vague language, hold a multi-step plan in working memory, or safely explore a codebase to find "the right place" for a change. They do well when told exactly: open this file, find this exact text, replace it with this exact text, run this exact command, check for this exact result.

Every ambiguity left in a ticket becomes a failure point for a small model. The job of this skill is to do all the exploration, decision-making, and disambiguation up front — in this conversation, with a capable model — so the small model's job becomes close to mechanical execution.

This applies regardless of language or stack. The patterns below (exact find/replace text, exact file paths, exact commands) work the same whether the codebase is TypeScript, Python, Go, Rust, Java, C++, or anything else — adapt the syntax of the code blocks and the verification commands to whatever the project actually uses, but keep the same level of explicitness.

## Process

### 1. Understand the ticket
Read it fully. Identify the goal, the definition of done, and any explicit constraints. Read any linked context that's available (docs, prior discussion, related tickets).

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
**File:** `path/to/file.ts` (create | modify | delete)
[If modify: exact old code block → exact new code block]
[If create: full file contents]
**Verify:** [exact command + expected result]

### Step 2: ...

## Final check
[command(s) confirming the whole ticket is done]
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

- **Don't let steps balloon.** More than one find/replace pair, or more than one file, means split the step.
- **Name exact identifiers.** Function names, variables, file paths, config keys — never "the config file" or "the relevant handler."
- **State non-obvious ordering explicitly** ("must run after Step 3 because it imports the type added there").
- **Don't assume the small model can search well.** Give it the exact search string or location instead of "find where X happens."
- **Use exact commands, not descriptions of commands** — `npm run test:unit` or `go test ./...` or `mvn -q test`, not "run the tests."
- **Match the language's own idioms.** Don't force a step's code onto a pattern from a different ecosystem (e.g. don't write Python error handling like it's JavaScript). Base every snippet on the actual surrounding code you read in step 2.
- **Watch for scope creep.** If investigating the codebase reveals the ticket is bigger than it reads, say so up front rather than silently producing a sprawling plan — flag it to the user before smallifying the whole thing.
