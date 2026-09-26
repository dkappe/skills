---
name: smallify
description: Break down a ticket, task, or feature request into an extremely explicit, granular, step-by-step implementation plan suitable for execution by a small, local, or otherwise weaker LLM with limited reasoning and context. Use this whenever the user asks to "smallify" a ticket, wants a task "dumbed down" or "spelled out," is prepping work for a local/open-source/lightweight coding model, or asks for maximally explicit steps that name exact files, functions, and code changes for an implementation task. The skill never prototypes, runs, or implements any code, and never produces findings summaries or status reports — the rewritten ticket file is its only artifact, and the plan it produces contains algorithm and code hints only — never paste-ready code, because the small model executing the plan writes all of the code.
---

# Smallify

Turn a ticket into a plan a small model can execute without having to think.

## Why this matters

Small and local LLMs don't have the reasoning capacity to fill in gaps, infer intent from vague language, hold a multi-step plan in working memory, or safely explore a codebase to find "the right place" for a change. They do well when told exactly: open this file, change this named function, make it do this described thing, run this exact command, check for this exact result.

Every ambiguity left in a ticket becomes a failure point for a small model. The job of this skill is to do all the exploration, decision-making, and disambiguation up front — in this conversation, with a capable model — so the small model's job becomes close to mechanical execution.

This applies regardless of language or stack. The patterns below (precise pointers, exact file paths, exact commands) work the same whether the codebase is TypeScript, Python, Go, Rust, Java, C++, or anything else — adapt the verification commands to whatever the project actually uses, but keep the same level of explicitness.

This skill only produces the plan. It doesn't touch the codebase — and it doesn't write, prototype, scaffold, or execute any code anywhere, not even in scratch files, throwaway scripts, or REPL sessions to "check the idea works." The only file it modifies is the ticket itself. The sole exception is empirical verification explicitly authorized by the user in-session under the protocol in "Empirical verification" below; without that explicit authorization, the rule above is absolute. Most empirical urges are resolvable without running anything — see the decision tree in "Empirical verification" (read harder; a plan check already guards it; pin-and-escalate) — and unauthorized probing is never the cheaper path: the disclosure, re-run, and reconstruction it forces cost more than every fallback combined. If you notice you've started implementing (writing a function body, drafting a module, running code to validate an approach), stop — that's this skill's failure mode, not part of it. If instead you notice you've started *investigating while the ticket file is still the original stub*, also stop and seed first — that's the other failure mode (see Iron rules).

This skill never produces findings summaries, status reports, or handoff documents — in chat or as side files (canonical rule: "Iron rules" above). The ticket file is the sole artifact; every decision, finding, and open question lives there (see steps 2 and 9).

## Iron rules

These override everything else in this file. They are stated here, at the top, because long runs lose context — these are the rules that must survive:

1. **The ticket file is the only artifact.** Every decision, finding, and open question is written into the ticket file on disk as it is made — never only in chat. The skill never produces findings summaries, status reports, or handoff documents, in chat or as side files.
2. **Seed before investigating.** The ticket file is rewritten into the output-format skeleton *before any codebase reading begins* (step 2). A run that investigates while the ticket file is still the original stub has already failed, however good its findings.
3. **Write each decision into the ticket as it's reached**, not in a batch at the end.
4. **Never write findings or status content in chat.** If you catch yourself drafting a findings-so-far block — in chat or as a side file — stop and move that content into the ticket instead. The one sanctioned chat content is a question round (step 3), and its questions are mirrored into the ticket's `## Open questions` section before you ask.
5. **An unfinished run marks itself in the ticket** (`## Smallify status: incomplete — steps N–9 remaining`, step 9) and gets at most one chat line pointing at the file.
6. **The small model writes the code; the ticket only hints.** The ticket may contain identifiers, paths, commands, literal values, and plain-language algorithm hints. It may not contain code the executor could paste — no function bodies, no statements, no fenced code blocks except shell commands. The whole point of smallify is to offload code generation to the small model; a ticket full of code means the expensive model did the cheap model's job. See "Code-hint budget" in step 5.
7. **Owner decisions are asked, not guessed.** Architecture forks, requirement gaps, and acceptance bounds go to the user as a question round with options, trade-offs, and a recommendation (step 3). Mechanical calls are never asked.

## Process

### 1. Understand the ticket
Read it fully. Identify the goal, the definition of done, and any explicit constraints. Read any linked context that's available (docs, prior discussion, related tickets).

Check for existing ticket metadata — a YAML front matter block, or key-value fields like `Status:`, `Priority:`, `Assignee:`, `Blocked by:`, `Labels:`, `Sprint:`, `Due:`, ticket IDs, links to related tickets, and so on. Note every such field verbatim; you'll carry it forward untouched in step 8. Don't infer or invent fields the ticket doesn't have.

### 2. Seed the ticket, then investigate the codebase (read-only)
This is the most important step — don't skip or approximate it.

**Gate — seed before you read anything.** Rewrite the ticket file into the output-format skeleton (metadata verbatim, Goal, empty Assumptions/Steps), preserving the stub's original body under a temporary `## Original (pre-rewrite)` heading so nothing is lost. From this moment the ticket file is the running record — every decision lands in it as it is made, never only in chat. Tripwire: if you notice you've begun investigating while the ticket file is still the original stub, stop — that's this skill's failure mode, not part of it. Seed first, then continue.

Investigation is read-only (sole exception: the authorization protocol in "Empirical verification"). Understanding comes from reading the actual code, not from executing something you wrote.
- Search for and open every file the ticket touches, even implicitly.
- Read the *actual current code*, not remembered or assumed code — exact function signatures, imports, naming conventions, nearby style. Reading test files beats running them; run the project's existing test suite only if the plan's verification design depends on knowing its current pass/fail state.
- Identify every file that needs to change. Don't leave "find the right place" as a task for the small model — that's your job now.
- If you catch yourself wanting to write or run code to answer a question, stop: work through the decision tree at the top of "Empirical verification" before anything else.

### 3. Resolve ambiguity at the right level — don't guess, don't over-ask
Never let an ambiguous instruction pass through to the small model — it will guess, and guess wrong. But resolving it *yourself* is not the only correct move; the question is who owns the choice.

**Self-resolve the mechanical calls:** file placement, names of new files/functions, which existing helper to reuse, purely internal constants, anything where every reasonable choice is equally fine. Pick one, pin it, record it as an Assumption. Don't spend user attention on these.

**Ask the user** when the choice belongs to the ticket owner, not to you:
- the choice forks the design: two materially different architectures are both reasonable;
- a requirement is missing or ambiguous: the ticket doesn't say what should happen in a case the code will have to handle;
- it sets an acceptance criterion: a tolerance, bound, or threshold that decides pass/fail for the whole ticket (this includes the tolerances and bounds themselves — "is ±0.005 right?" is a design fork only the ticket owner can answer);
- it touches user-visible behavior or a public interface;
- your preferred reading contradicts, narrows, or extends what the ticket literally says;
- a wrong guess would be silent and structural (the probe decision tree in "Empirical verification" applies here too);
- investigation shows the ticket is much bigger than it reads (scope — see "Things to watch for").

If a fact can be settled from the code, docs, config, or git history, settle it yourself — questions are for *choices*, not for facts you could have read.

#### Question rounds (grill-style)

Treat the open choices as a **design tree**: some decisions only make sense once a parent decision is settled (e.g. "which cache eviction policy" depends on "cache in-process or in Redis"). Ask in rounds:

1. **Map the tree** after the first investigation pass. List every owner decision and what it depends on.
2. **Ask only the frontier** — decisions whose parents are already settled. Never ask a question in the same round as the question it depends on; its options would be guesses.
3. **Batch the whole frontier into one round.** No drip-feed of one question per discovery. Typical round: 2–5 questions. Fold any probe-authorization request (see "Empirical verification") into the first round.
4. **Before sending a round, write its questions into the ticket** under `## Open questions`, each with its recommended default. If the session dies while waiting, the next run finds them there.
5. **When answers arrive**, write each one into the ticket immediately as a pinned fact (in the relevant step or in Assumptions, tagged `(owner decision, Q<N>)`), remove it from Open questions, then recompute the frontier. Children of an answered question may now be askable, or may have vanished.
6. **Repeat until the frontier is empty**, then continue straight into the rewrite. If you need more than 3 rounds, the ticket is under-specified: say so in the next round and offer to smallify only the settled part.

**Question format.** Every question follows this shape, so the user can answer with a letter:

    ❓ Q<N> — <short title>
    Context: <1–3 sentences: what you found, naming files/identifiers, and why it forces a choice>
    Options:
      A. <option> — <what it means for the plan; main trade-off>
      B. <option> — <what it means for the plan; main trade-off>
      [C./D. only if genuinely distinct]
    ➡️ Recommendation: <letter> — <one or two sentences of reasoning grounded in what you read>
    If unanswered: <letter> is pinned as an Assumption; <the plan check that fails loudly if it's wrong>
    Unblocks: <which steps, and which later questions, depend on this>

Options must be concrete and mutually exclusive — each one something the plan could actually be written around. Don't pad with straw-man options to make the recommendation look good; two real options beat four fake ones. Numeric bounds get a concrete recommended number, not a range. If the environment offers a structured multiple-choice question tool, use it for the options and keep Context and Recommendation in the question text.

Let the user answer compactly: "Q1 B, Q2 recommended, Q3 A but with X" is a complete answer. "Go with your recommendations" accepts every recommendation in the round. Silence or deflection means each recommendation becomes an Assumption in pin-and-escalate form — never a silent decision. An answer that invalidates a previous answer reopens that branch of the tree; update the ticket before asking the next round.

**If the turn must end before the answer arrives** (user away, context dying, session ending), do not leave the question open: pin-and-escalate immediately — the concrete guess as an Assumption, the plan check that fails loudly if the guess is wrong, and the mechanical escalation rule (who re-runs smallify, what evidence triggers the change). An undecided bound, tolerance, or design choice at end of turn is a failed run. The only valid endings are: asked (a question round, mirrored in `## Open questions`), pinned (Assumption), or escalated — never deferred. A resumed run that finds `## Open questions` with no answers in chat asks them again once; if still unanswered, it pins the recommended defaults.

**Decisions made during investigation are not done until they're in the plan.** Every choice you reach while reading the codebase — which helper to call, which mapping route to use, what numeric tolerance applies, what format data crosses a language or process boundary in — must appear in the rewritten ticket as a pinned fact or an Assumption. A summary "of what was learned" that lives outside the ticket is lost the moment the session ends; the ticket is the only artifact that reaches the small model. Corollary: the skill is not finished when the investigation is finished — it is finished when the ticket is rewritten (step 9). Do not stop after investigation to report findings and wait; carry the decisions straight into the rewrite in the same session. Only pause for the question rounds described above — and if you have nothing to ask, don't pause at all.

**Write decisions into the ticket file as you reach them, incrementally — not in one batch at the end.** At every moment, the ticket on disk contains everything decided so far. The batch-at-the-end rewrite is how work evaporates when a session dies mid-investigation.

### 4. Decompose into atomic steps
- One step = one coherent, independently verifiable change. If a step's description contains "and," consider splitting it.
- Order steps by dependency (define a type before using it, add a migration before code that queries the new column, etc).
- Each step must be self-contained: don't assume the small model remembers *why* earlier steps happened, only their file-system effects.

### 5. Point to exactly what needs to change — with code hints, not code
Every step should name a location so precisely that there's no exploration or invention involved, but describe the *change*, not the implementation:
- **Create** — full path, plus a precise description of the file's purpose: what it should export/contain, what it depends on, roughly how it fits into the surrounding code. Not the file's contents.
- **Modify** — full path, plus an exact anchor (function/class name, line range, or "directly above/below X") locating the spot, and a plain-language description of the required behavior change.
- **Delete** — full path, plus a check (or a prior step) confirming nothing else still imports or references it.
- **Rename/move** — treat as create + delete pointers, and list every other file that imports the old path.

The description should be specific enough that the small model has only one reasonable *behavior* to implement — no design decisions left open. It does not need to pin the *code*: two implementations that differ only in syntax, local variable names, or loop style are both fine, and choosing between them is exactly the work being handed to the small model. Design decisions (which helper, which data structure, which algorithm, which error, which bound) must be pinned; code-level choices must not be.

#### Code-hint budget

This is the line that matters most in step 5, and the one most often crossed, because the fastest way to make a step unambiguous is to write the code. Don't. Make it unambiguous with names and plain language instead.

**Allowed in the ticket:**
- Inline code spans for things that already exist or that you are naming: file paths, function/class/variable names, config keys, type names, signatures to mirror (`parse_row(line: str) -> Row`), error class names.
- Literal values the spec depends on: constants, thresholds, format strings (`%.17g`), regexes the behavior is defined by, expected test values, exact CLI commands.
- **Algorithm hints** in plain language (format below) — this is the sanctioned way to convey a non-trivial algorithm.

**Not allowed in the ticket:**
- Fenced code blocks, except shell commands under **Verify:** / **Final check**.
- Function or method bodies, in any language or pseudo-language.
- Complete statements or expressions (`if (!user) throw ...`, `return sorted(xs, key=...)`), even one line.
- "Pseudocode" that is really code: braces, `def`/`function`, assignment syntax, language keywords. If it would nearly compile, it is code.
- Test bodies. Describe cases and assertions in words plus the literal expected values.

**Algorithm hint format.** When a step needs a non-trivial algorithm, write it as a short numbered list in prose inside the step, under `Algorithm hint:`:
- name the input(s) and output by identifier;
- name the data structure(s) to use and why (e.g. "a dict keyed by `order_id`");
- give the steps as sentences, at most about 8;
- state edge cases and invariants explicitly (empty input, duplicates, off-by-one, ordering);
- optionally state the target complexity.

The executor turns the sentences into code. If your hint has more than ~8 steps, the step is too big — split it.

**Self-check before writing each step:** could the small model copy any part of this step into the source file with only whitespace changes? If yes, rewrite that part as intent + identifiers. Could it misunderstand *what* to do? If yes, add names, values, or an algorithm hint — not code.

### 6. Give every step a verification action
Small models don't reliably self-check. Attach to each step (or small cluster of steps):
- An exact command to run (`npm test path/to/file.test.ts`, `pytest tests/test_x.py::test_y`)
- What "pass" looks like (exit code 0, a specific assertion, no new lint errors)

If the ticket has no tests, decide where a test belongs and describe the new test as its own step — its file path, the test function names, the cases it must cover (with literal inputs and expected outputs), and the assertions in plain language. Do not write the test code itself; the same code-hint budget applies to tests. Point at an existing test in the same file or directory as the pattern to follow instead of writing one out.

### 7. Close with an overall acceptance check
End with a final step tied to the ticket's definition of done — e.g. "run the full test suite" or "start the app and confirm X happens."

### 8. Carry forward the ticket's own metadata, unchanged
If the original ticket had a metadata block (YAML front matter, or fields like `Status:`, `Priority:`, `Assignee:`, `Blocked by:`, `Labels:`, `Sprint:`, ticket ID, etc.), reproduce it at the top of the rewritten ticket exactly as it was — same fields, same values. This is tracking data owned by whatever system the ticket lives in; smallify's job is to make the *body* explicit, not to touch, reinterpret, or invent tracking fields. If the ticket had no metadata, don't add any. Copying metadata is not an ending: the run ends only when step 9's rewrite is complete in the same session.

### 9. Finish in-session: write the ticket, don't hand back a summary
The deliverable of this skill is the rewritten ticket file — not a status report, not a summary of findings, not "investigation done, rewrite pending." Completing investigation or design does not complete the skill. Before ending your turn, write the ticket rewrite (the format below) into the ticket file itself, including every decision from step 3. Never leave the original ticket in place while the plan exists only in conversation.

**If you cannot finish in this turn** (context limits, user ends the session, environment dies):
- Before stopping, the ticket file must contain everything decided so far — pinned facts and Assumptions included — and a line `## Smallify status: incomplete — steps N–9 remaining` naming exactly what's left.
- **Forbidden: writing findings, status, or "session summary" content anywhere except the ticket file.** No chat summaries of findings, no `error.md`/notes files, no "handoff documents." If you catch yourself drafting a findings-so-far block — in chat or as a file — stop and move that content into the ticket instead. Chat-only summaries and side-file summaries are both failed runs, because the next session's only guaranteed input is the ticket file on disk.
- At most, one chat line pointing at the ticket: "smallify incomplete; ticket rewritten through step N, see file." A chat-only summary is a failed run, because it evaporates.

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

## Open questions
[Only while a question round is pending: each question in the step 3 format, with its recommended default. Must be empty/removed in a finished ticket.]

## Assumptions
[Interpretation calls you made, stated plainly, and owner decisions tagged `(owner decision, Q<N>)`. Omit if none.]

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

## Every-turn gate

At the end of *every* turn during a smallify run — not only the final one — check before responding: does the ticket file on disk contain everything decided so far? If not, write it first. Runs end at any turn boundary (context limits, user exit, crash, compaction); only what is in the file survives. A turn that ends with decisions living only in chat is a failed turn.

## Done means

The run is complete only when all of the following are true. Check them before ending your turn:

- [ ] The ticket file on disk contains the rewritten plan (not the original stub, not a diff description of it). Check: open the file; if it is still the stub, or the plan exists only in this conversation, this box fails.
- [ ] Every decision made during investigation appears in the ticket — as a pinned fact in a step or as an Assumption. Check: reread the ticket file; anything stated only in this conversation fails this box.
- [ ] If the run ended incomplete, the ticket file contains the `## Smallify status: incomplete — steps N–9 remaining` line from step 9; if the run is complete, that line is absent.
- [ ] Every file path, function/identifier name, command, and cross-component data format in the plan is exact and final. Check: search the ticket for "e.g.", "TBD", "to be decided at execution time", and placeholder names — none remain.
- [ ] Every numeric comparison bound is a concrete number, stated in the plan.
- [ ] Every owner decision (architecture fork, requirement gap, acceptance bound, public behavior) was either answered by the user or pinned from its recommendation as an Assumption, and the finished ticket has no `## Open questions` section. No mechanical call was sent to the user.
- [ ] Ticket metadata was carried forward verbatim (or the ticket had none and none was added).
- [ ] No code was written, prototyped, or implemented anywhere, and no new code was executed — investigation was read-only. The only exceptions: (a) a run of the project's existing test suite under step 2's conditional clause, or (b) user-authorized probes, in which case this box instead requires full compliance with the "Empirical verification" rules, including the disclosure section.
- [ ] If empirical verification was authorized and used: authorization was requested first, as one batched enumeration of every empirical question; probe artifacts are saved as re-runnable files in scratch (not left as transcript-only heredocs); the ticket contains the disclosure section mapping each question → probe → pinned fact. If it was not authorized, none was done — asking-first was not skipped, and no probe ran on the model's own judgment.
- [ ] The ticket contains no paste-ready code. Check: search the ticket for ``` fences — every one must hold only shell commands under **Verify:** or **Final check**; scan each step for function bodies, complete statements, or pseudocode with language syntax. Algorithm hints are plain-language numbered sentences. Any hit fails this box — rewrite it as intent + identifiers.
- [ ] No findings, status, or session-summary content exists anywhere except the ticket file. Check: no summary blocks in chat, no notes/handoff side files created during the run.

If any box is unchecked, the skill is not done — finish it before responding to the user. A reply that summarizes "what the plan will contain" instead of containing it is a failed run.

## Empirical verification (opt-in, user-authorized only)

The read-only rule has one exception. The user may explicitly authorize running probe code during investigation — for example to measure a numeric tolerance against real data, or to confirm that a suspected encoding bug is real. "Explicitly authorized" means the user said so in the current session, before any code is written or run: a standing rule from a past session, a repo convention, a sibling ticket's style, or an inference from the ticket's own wording ("unless real numbers are in hand") is NOT authorization. Assume no until told yes.

**Before considering a probe at all, work this decision tree, in order:**

1. **Can more reading answer it?** Counting occurrences (`grep -c`), checking for string presence, parsing a data file mentally from its contents, reading the code that generates the data — these are all reading, and they answer most questions. Do that.
2. **Does the plan already contain a check that fails loudly if this fact is wrong?** Pin the assumption, cite the check, move on. **A probe that duplicates a check already in the plan is pure waste** — it adds cost and zero safety.
3. **Is a wrong guess cheaply recoverable?** If the executor's verification would fail and trigger a re-run of smallify with evidence, that fallback is almost always cheaper than a probe. Use the pin-and-escalate template below.
4. **Only if a wrong guess would be silent (pass every check while implementing the wrong thing) and structural (invalidate the comparison design itself), request authorization** for that specific question, batched as described below.

Before writing any probe, state in one sentence: which decision it unblocks, and what the fallback costs. If the fallback is "a verification step fails → re-run smallify," the fallback is cheaper.

**Batched authorization.** Probe authorization is requested as part of step 3's first question round, not separately: enumerate every open empirical question, what each unblocks, and the fallback for each. One "yes" covers exactly the enumerated list; anything discovered later is a new explicit ask or falls back to read-only. Silence or deflection is no. If the user says no or doesn't answer, pin a concrete initial bound plus a mechanical escalation rule (per "Things to watch for") and let the executor's verification step surface mismatches. If the turn must end before the user answers, do the same immediately — an open empirical question at end of turn follows pin-and-escalate, never deferral.

When authorized, the protocol is:

1. **Write and run probes only in the user's designated scratch area** (e.g. `/tmp`), never in the repo tree. If no scratch area was named, ask or use the system's standard temp directory.
2. **The repo working tree must not be modified at any point, even temporarily.** No editing repo source files to test a fix, no `git checkout` restore cycles. A probe that needs modified source is copied to scratch with its imports adjusted. If that's impossible, the probe doesn't run and the plan carries the open question instead.
3. **Probes parse data; they never exercise the change.** Probes may read and parse existing checked-in files to pin facts (counts, formats, sums, index conventions). Building repo code or running it to observe behavior — with or without modifications — is not investigation; it is testing, and it belongs to the executor. (Reading test files is preferred over running them; run the suite only if the plan's verification design depends on knowing its current pass/fail state.) A probe that needs modified source is impossible under this rule.
4. **No code from the probes may leak into the plan as implementation.** The plan still follows the code-hints rule: probes inform pinned facts, tolerances, and bug findings, not paste-ready code. If probing led you to essentially write the implementation (e.g. a complete new test file), the plan must still present it at hint level — file purpose, anchors, required behavior, cases to cover — and the executor writes the code.
5. **Negative-control anything the plan will rely on.** A check that cannot fail proves nothing: deliberately break the input or tighten the bound past the margin and confirm the comparison actually flags it. Record both numbers (pass and failure counts).
6. **Record probes as re-runnable artifacts in scratch**: one script or command sequence that reproduces every number the plan pins. Name it in the plan so the user or executor can re-run it. Do not leave "the transcript is the record" — if a probe was worth running, it is worth one saved, re-runnable file.
7. **Disclose in the ticket.** Add a `## Verified during smallify` section listing every file written, every command run, and which pinned facts in the plan rest on them, plus the command to re-run the probes. Map each question → probe → pinned fact. A ticket that relies on probe results without this section is a failed run.

**Pin-and-escalate template** (the sanctioned alternative to probing): (a) state the concrete guess as an Assumption; (b) name the plan check that fails loudly if the guess is wrong; (c) give the mechanical escalation rule — who re-runs smallify and what evidence triggers the change. Every unresolved-at-investigation fact must take this form.

Empirical verification changes how facts are obtained, not the skill's deliverable: the rewritten ticket, in the file, in-session, remains the finish line.

## Example: good vs. bad step

**Good — precise pointer, hint-level detail, no implementation, works in any language:**

    **File:** `src/api/users.ts` (modify)
    Anchor: the `getUser` function.
    Change: after the existing lookup call, check whether the result is null/undefined. If so, throw a `NotFoundError` whose message includes the requested id. Otherwise return the user as before, unchanged.
    **Verify:** `npm test src/api/users.test.ts` — the new "throws NotFoundError for missing user" test passes.

    **File:** `api/users.py` (modify)
    Anchor: the `get_user` function.
    Change: after the existing lookup, check whether the result is `None`. If so, raise `NotFoundError` with a message that includes the user id. Otherwise return the user unchanged.
    **Verify:** `pytest tests/test_users.py::test_get_user_raises_when_missing` passes.

**Bad — too vague, leaves a design decision open:**

    Update the user fetching logic to handle missing users.

**Also bad — too much, spells out the implementation (or prototypes it):**

    Replace the function body with:
    ```ts
    export function getUser(id: string) {
      const user = db.users.find(id);
      if (!user) throw new NotFoundError(`User ${id} not found`);
      return user;
    }
    ```

    (The same failure even when it's outside the ticket — e.g. drafting the new `getUser` in a scratch file to run it before writing the plan. Don't prototype; hint. Sole exception: user-authorized probes under the protocol above, which stay in scratch and out of the plan.)

**Good hint-level alternative to the above:**

    **File:** `src/api/users.ts` (modify)
    Anchor: the `getUser` function.
    Change: after the existing lookup, handle a missing user by throwing the existing `NotFoundError` class with a message including the id. Reuse the lookup call and error class already present in this module; do not restructure the function.
    **Verify:** `npm test src/api/users.test.ts` — the new "throws NotFoundError for missing user" test passes.

**Good — algorithm hint for a non-trivial change:**

    **File:** `src/billing/merge.py` (modify)
    Anchor: the `merge_invoices` function.
    Change: replace the current pairwise comparison with a single-pass merge keyed by customer.
    Algorithm hint:
    1. Build a dict keyed by `invoice.customer_id`, value = list of that customer's invoices.
    2. For each key, sort its list by `issued_at` ascending.
    3. Walk the sorted list; when two consecutive invoices have `issued_at` within `MERGE_WINDOW` (existing constant, 24h), combine them with the existing `Invoice.combine` method; otherwise start a new group.
    4. Return all resulting invoices, ordered by `customer_id`, then `issued_at`.
    Edge cases: empty input returns an empty list; a customer with one invoice passes through unchanged; exactly-24h apart counts as within the window.
    **Verify:** `pytest tests/billing/test_merge.py` passes, including the new `test_merge_window_boundary`.

**Bad — the same thing as "pseudocode" that is really code:**

    by_cust = defaultdict(list)
    for inv in invoices: by_cust[inv.customer_id].append(inv)
    for cid, lst in by_cust.items():
        lst.sort(key=lambda i: i.issued_at)
        ...

The commands you attach as verification should match the project's own ecosystem — `go test ./...`, `cargo test`, `mvn test`, `pytest`, `npm test`, whatever the repo actually uses. Check the repo (build files, CI config, README) rather than assuming.

## Things to watch for

- **This skill's rules take precedence over repo precedent.** Earlier tickets in the same repo may have been produced under different conventions (e.g. shipping verbatim pre-compiled code, or claiming "verified during smallification"). Those conventions do not amend this skill. If following this skill would contradict how sibling tickets were produced, do not silently resolve the conflict: either ask the user (in a step 3 question round), or follow this skill and note the divergence in an Assumption. Never cite a sibling ticket's style as authorization for anything this skill forbids.
- **Preserve ticket metadata, don't reinterpret it.** Whatever status/priority/blocker/assignee fields the original ticket had, copy them forward as-is. Don't mark something "blocked" or change its status based on your own read of the work — that's not smallify's call to make.
- **Don't invent tracking fields.** If the ticket had no metadata block, the rewritten ticket gets none either.
- **Describe the change, don't write it.** Name the exact file and anchor, and state the required behavior precisely enough that only one *behavior* is reasonable — but leave the actual code to the model executing the plan. Names, anchors, "reuse X", literal values, and plain-language algorithm hints are allowed; bodies, statements, pseudocode-that-compiles, and code blocks are not (see "Code-hint budget").
- **Precision pressure is not a license to code.** When a rule in this file demands exactness (data formats, conversions, bounds), satisfy it with a named identifier, a literal value, or a format string — never by writing the code that produces it.
- **Never prototype or run code — including for tests.** Canonical rule at the top of this file; the only exceptions are step 2's conditional existing-suite run and user-authorized empirical verification (see above). The first time any code you wrote exists anywhere without that authorization, the skill has failed.
- **A probe that duplicates a plan check is pure waste.** If the executor's verification (consistency check, per-FEN assertion, tolerance bound) would catch the fact being wrong, probing adds cost and zero safety. Before any probe, name the plan check that already covers it — if you can't, that's a gap in the plan, fix the plan, not a probe.
- **Don't touch the codebase.** This skill only produces the plan; the ticket is the only file it edits.
- **Don't let steps balloon.** More than one change, or more than one file, means split the step.
- **Name exact identifiers.** Function names, variables, file paths, config keys — never "the config file" or "the relevant handler."
- **State non-obvious ordering explicitly** ("must run after Step 3 because it imports the type added there").
- **Don't assume the small model can search well.** Give it the exact search string or location instead of "find where X happens."
- **Use exact commands, not descriptions of commands** — `npm run test:unit` or `go test ./...` or `mvn -q test`, not "run the tests."
- **Pin every artifact name — "e.g." is not a plan.** File names, tool names, and function names chosen during design must be stated as final in the ticket. Write `tools/oracle_check.py (create)`, not "a Python checker (e.g. `tools/oracle_check.py`)". If you can't commit to a name, you haven't finished deciding.
- **No deferred decisions or adjustable tolerances.** Every bound, threshold, or precision in the plan is one concrete number chosen by you, stated in the plan. Never write "the exact bound will be finalized based on the first run" — that delegates a judgment call to the small model. If a bound may need revisiting after real data, state the concrete initial bound plus a mechanical escalation rule (who re-runs smallify, what evidence triggers the change), not an open choice for the executor.
- **Specify cross-language/cross-process data exchange exactly.** Wherever the plan has one program emitting data for another to consume (C binary → Python checker, service → client, tool → script), the plan must pin the exact format: line format, field order, and print precision. Float precision is the classic silent failure — default `printf` rounding can create comparison failures that look like numeric bugs. Name the exact conversion (e.g. a shortest-round-trip formatting routine, or a literal format string like `%.17g`) rather than "print the values" — as a spec, not as the print statement itself.
- **One route per mapping, named.** When more than one existing mechanism could accomplish a mapping (two helper functions, two data sources), the plan must name exactly one — with the reason the other was rejected — so the small model never chooses between them.
- **Watch for scope creep.** If investigating the codebase reveals the ticket is bigger than it reads, say so up front rather than silently producing a sprawling plan — flag it to the user as a question in the first round (options such as: smallify all of it, split into tickets, smallify only part X) before smallifying the whole thing.
