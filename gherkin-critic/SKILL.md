---
name: gherkin-critic
description: Audit existing Gherkin feature files, Cucumber.js step definitions, and Playwright/World setup against gherkin-genius's standards, and write the findings to a single markdown report. Use this whenever the user asks to review, audit, critique, or analyze existing BDD/Cucumber/Playwright tests, check test coverage against a ticket or spec, or find steps that aren't real UI-layer Playwright tests (steps that import application code, hit a database or internal API directly, manipulate localStorage/sessionStorage/cookies/IndexedDB as a shortcut, or assert on app/store/storage state instead of the rendered page). This skill is read-only except for the one report file it writes — it never edits, fixes, or deletes a feature file, step definition, or support file. Use gherkin-genius alongside this skill when the user wants the flaws actually fixed, not just reported.
---

# Gherkin Critic

Audit a Cucumber/Playwright BDD suite against gherkin-genius's standards. Report only — never fix.

## Relationship to gherkin-genius

gherkin-genius defines what a good Gherkin/Cucumber-js/Playwright UI test looks like: declarative scenarios, thin Playwright-only step definitions, isolated browser contexts, no reaching into application internals, no non-UI assertions. gherkin-critic applies that same rubric in reverse — it reads what already exists and reports where it falls short. If the user wants issues actually corrected, that's a separate follow-up using gherkin-genius; this skill doesn't make edits.

## Hard constraint: read-only except for one output file

This skill:
- **Reads** `.feature` files, step definitions, support/World/hook files, and cucumber config.
- **May run non-mutating checks** — e.g. a cucumber-js dry run (`--dry-run`) to surface undefined/ambiguous steps — since a dry run doesn't execute step bodies or touch the app.
- **Writes exactly one file**: the markdown report, at the path the user specified. If no path was given, ask for one rather than guessing, since this is the one file-write this skill performs and getting it wrong means output lands somewhere the user didn't intend.
- **Never** edits, fixes, deletes, or reformats any `.feature` file, step definition, support file, or config — even for a one-line, obviously-correct fix. Note the fix in the report instead.
- **Never runs the actual scenarios end-to-end** unless the user explicitly asks for that — full execution can have side effects on app/test-data state, and it's outside "analyze and report" scope by default.

## Process

### 1. Establish scope
Find every `.feature` file, every step definition file, the support/`World` setup, and the cucumber config (`cucumber.js`/`cucumber.json`). If the user pointed at a specific ticket, feature area, or subset of files, scope the audit to that; otherwise audit everything found.

### 2. Read everything before judging anything
Read the actual current content of each file — don't infer step behavior from its name. A step named `Given the user is logged in` could be driving a real login form, or it could be a one-line `page.evaluate(() => localStorage.setItem('auth_token', ...))` that fakes the outcome without ever touching the login UI. You can only tell which by reading the step definition body — the step name alone tells you nothing.

### 3. Check each step definition against the UI-layer rule
For every step definition, determine whether it:
- Interacts with the app **only** through a Playwright `Page`/locator/page-object call — flag anything that imports application source (services, controllers, models, reducers, business logic) directly.
- Avoids direct database or internal-API calls used as a shortcut past the UI (raw SQL/ORM calls, `fetch`/`axios`/`supertest` hitting an internal endpoint instead of the browser navigating there) — unless the scenario's actual subject is that API, which is itself worth flagging as probably belonging in a different suite.
- Avoids manipulating browser storage as a shortcut — `page.evaluate()` writing to `localStorage`/`sessionStorage`, `context.addCookies()`, `addInitScript()` planting a token, or direct IndexedDB writes, used in place of a real UI flow (login, adding items to a cart, accepting a consent banner, etc.). This is a common one to miss because it still runs through Playwright APIs and looks "legitimate" at a glance — check what the `page.evaluate`/`addCookies` call is actually *for*, not just whether Playwright is present in the file.
- Asserts against what's rendered on the page, not against application/store/database state or browser storage (`expect(store.getState()...)`, reading a model directly, `page.evaluate(() => localStorage.getItem(...))` used as the assertion instead of what the UI shows).
- Runs on a Playwright-launched browser (`chromium`/`firefox`/`webkit`) — flag any use of Puppeteer, Selenium/WebDriver, jsdom, or a plain HTTP client standing in as the driver.
- Doesn't rely on manual sleeps (`waitForTimeout`) papering over a race condition.

### 4. Check each feature file against Gherkin style
- Imperative vs. declarative: flag scenarios describing clicks/CSS/field IDs instead of behavior.
- One behavior per scenario: flag scenarios covering multiple unrelated outcomes.
- Reuse: flag near-duplicate steps that could be one parameterized step.
- `Background` used only for setup shared by every scenario in the file, not just some.
- Tags consistent with whatever vocabulary the rest of the suite already uses.

### 5. Check coverage
- Cross-reference feature files against the ticket, spec, or acceptance criteria the user points to (if any) — list acceptance criteria with no corresponding scenario, and scenarios with no traceable requirement behind them.
- Look for missing negative/edge-case paths next to a happy-path scenario (e.g. only the successful checkout is covered, not a declined payment).
- Run a cucumber-js dry run if available, to catch undefined steps, ambiguous step matches, and steps defined but never referenced by any scenario.

### 6. Categorize findings by severity
- **Blocking** — the step isn't actually testing the UI at all (bypasses the browser, wrong driver, asserts on internals). These undermine what the suite claims to verify.
- **Major** — real coverage gaps (missing acceptance criteria, missing negative paths) or structural problems (imperative scenarios, oversized scenarios).
- **Minor** — style/consistency issues (duplicate near-identical steps, inconsistent tagging, non-idiomatic step wording).

### 7. Write the report
Write findings to the specified markdown file. Nothing else changes.

## Report format

```markdown
# Gherkin/Cucumber/Playwright Audit — [scope: repo/feature area/ticket]

## Summary
[N] blocking, [N] major, [N] minor findings across [N] feature files and [N] step definition files.

## Blocking

### [Short title]
**File:** `path/to/file` (line [N] if known)
**Issue:** [what's wrong, quoting the offending code/step]
**Why it matters:** [what this means isn't actually being verified]

### ...

## Major

### [Short title]
**File / Scenario:** [location, or "no corresponding scenario" for a coverage gap]
**Issue:** [description]

### ...

## Minor

### [Short title]
**File:** `path/to/file`
**Issue:** [description]

### ...

## Coverage gaps
- [Acceptance criterion / behavior] — no scenario found
- ...

## Suggested next step
[e.g. "Re-run with gherkin-genius to fix the blocking items in features/checkout.feature first."]
```

## Things to watch for
- **Don't fix anything, even something trivial.** A one-character typo fix is still an edit; note it in the report instead.
- **Don't guess at an output path.** If the user didn't specify one, ask.
- **Don't judge a step by its name.** `Given the user is logged in` reads the same whether it drives a real login form or fakes it with a `localStorage`/cookie write — the step definition body is the only source of truth.
- **Distinguish "wrong driver" from "no driver yet."** A step definition with a `// TODO` and no implementation is a coverage gap, not necessarily a UI-layer violation — say which one it is.
- **Quote the actual offending line**, not a paraphrase — the report needs to be actionable without the reader re-reading every file themselves.
- **Don't inflate severity.** A step that reads slightly awkwardly is minor; a step that silently never touches the browser (including via a storage-manipulation shortcut) is blocking. Keep the categories meaningful so "blocking" doesn't get diluted.
