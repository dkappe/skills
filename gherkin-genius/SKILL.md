---
name: gherkin-genius
description: Write and improve Gherkin feature files, Cucumber.js step definitions, and Playwright-driven UI test automation, where every step drives the browser through Playwright rather than reaching into application code. Use this whenever a task involves creating or editing .feature files, writing or fixing cucumber-js step definitions, wiring Playwright into a Cucumber World/hooks setup, or turning a ticket's acceptance criteria into executable Gherkin UI scenarios. Applies during implementation work too — e.g. "implement ticket 06, use gherkin-genius where useful" means that whenever that implementation calls for a .feature file or a Cucumber/Playwright UI test, follow this skill for it; plain unit tests, non-UI integration tests, or non-test code aren't in scope.
---

# Gherkin Genius

Write Gherkin/Cucumber-js/Playwright tests that read like behavior, not like a script of clicks.

## When this applies

Reach for this skill specifically when the work involves:
- Writing or editing a `.feature` file
- Writing or editing cucumber-js step definitions (`features/step_definitions/**`)
- Setting up or touching the Cucumber `World`, hooks, or Playwright wiring (`features/support/**`)
- Converting a ticket's acceptance criteria into executable Gherkin scenarios

It doesn't apply to plain Playwright tests without Cucumber, unit tests, or implementation code that isn't test-related. If a ticket only needs those, skip this skill for that part.

## Core principle: scenarios describe behavior, not UI mechanics

A scenario should read the same whether the feature is a web app, an API, or a CLI. If a non-technical stakeholder can't read the scenario and confirm it matches what they asked for, it's written at the wrong level.

**Declarative (good):**
```gherkin
When the customer submits a payment with an expired card
Then the payment is declined
And the customer sees a message asking them to update their card
```

**Imperative (bad — describes clicks, not behavior):**
```gherkin
When the customer clicks the "Pay Now" button
And a modal appears
And the customer types "4000000000000069" into the card number field
And the customer clicks "Submit"
Then a red div with class "error-banner" is visible
```

The imperative version breaks the moment a selector or UI flow changes, and it hides *why* the scenario matters. Push the "how" (selectors, clicks, waits) down into step definitions and page objects — never into the feature file itself.

## Use modern Gherkin syntax, not just Given/When/Then

Gherkin has grown past the bare Feature/Scenario/Given-When-Then set. Use the fuller vocabulary where it actually clarifies structure:

- **`Rule`** — groups the scenarios that together implement one business rule. Use it when a feature has multiple distinct rules, each with its own scenarios, instead of one flat list of scenarios covering unrelated rules side by side. A `Rule` can have its own `Background` (setup shared only by scenarios under that rule) in addition to, or instead of, a feature-level `Background`.
  ```gherkin
  Feature: Checkout discounts

    Rule: Orders over $100 get free shipping

      Example: Order just over the threshold ships free
        Given a cart totaling $101
        When the customer checks out
        Then shipping is free

      Example: Order just under the threshold is charged shipping
        Given a cart totaling $99
        When the customer checks out
        Then shipping is charged at the standard rate

    Rule: First-time customers get 10% off
      ...
  ```
- **`Example` as a synonym for `Scenario`** — functionally identical; `Example` reads more naturally nested under `Rule`, since it's literally an example of that rule. Prefer whichever the project already uses consistently (check step 2); default to `Example` for new scenarios written under a `Rule`, and `Scenario` for standalone ones not grouped by a rule.
- **`*` for repeated steps of the same type** — when a scenario has several `Given`s (or several `And`s) in a row, `*` can replace the repeated keyword to reduce visual noise, especially for list-like setup:
  ```gherkin
  Scenario: Cart total reflects all items
    Given an empty cart
    * I add a "widget" for $10
    * I add a "gadget" for $25
    * I add a "gizmo" for $15
    Then the cart total is $50
  ```
  Don't overuse it — the first step of a sequence should still be `Given`/`When`/`Then` so the scenario's shape is legible at a glance; `*` is for the repeats, not the anchor step.

Don't introduce `Rule` or `*` into a project that doesn't already use them without checking in — see step 2. Some teams and tools (older IDE plugins, some reporting integrations) have partial or no support for `Rule`; if the project's tooling doesn't group by `Rule` in its reports, flag that before restructuring an existing feature file around it.

## Hard rule: every step drives the browser, nothing bypasses the UI

These are BDD tests of the UI layer, not integration tests wearing a Gherkin costume. Every step — including `Given` setup steps — must exercise the app the way a real user would: through Playwright interacting with the rendered page. That means:

- **No importing application source/modules into step definitions.** A step definition should never `import` the app's own services, controllers, reducers, or business logic to call them directly. Its only handle on the app is the Playwright `Page`.
- **No calling internal functions or hitting the database/service layer directly** to fabricate state, even for setup. If a scenario needs a logged-in user or existing data, get there by driving the UI (a real login flow, a real form submission) — or, if that's genuinely too slow to repeat per scenario, that's a call for the user to make explicitly, not a default this skill takes on its own.
- **No jumping straight to an internal API or GraphQL/REST endpoint to shortcut past the UI** as a substitute for interacting with it, unless the scenario's actual subject *is* that API — in which case it isn't a UI scenario and probably doesn't belong in this feature file at all.
- **Assertions read from the UI**, not from application state, a store, or a database row. `Then` steps check what's rendered on the page (text, visibility, an element's state) — not `expect(store.getState().foo).toBe(...)`.
- **The test runner is always Playwright.** Don't reach for Puppeteer, Selenium, jsdom, or a headless request client as the driver. Check the project's `cucumber.js`/support setup uses `playwright` (`chromium`/`firefox`/`webkit`.launch) — if it doesn't, that's a setup gap to flag, not something to work around with a different driver.

If following this strictly would make a scenario impractically slow or flaky (e.g. re-doing a multi-step signup flow before every scenario), say so explicitly rather than silently reaching into app internals to shortcut it — that's a decision for the person to make, not a default.

## Process

### 1. Find what "behavior" means here
Read the ticket's acceptance criteria (or the behavior being implemented). Identify the actor, the action, and the observable outcome. If acceptance criteria are already close to Given/When/Then, that's a strong signal they're meant to become scenarios — don't skip turning them into one just because it feels redundant.

### 2. Check the existing project conventions first
Before writing anything, look at:
- `cucumber.js` / `cucumber.json` config — paths, tags, formatters already in use
- An existing `.feature` file for tag conventions (`@smoke`, `@wip`), phrasing style, domain vocabulary, and whether the project already uses `Rule`/`Example`/`*` or sticks to plain `Scenario`/`Given`/`When`/`Then`
- `features/support/world.ts` (or similar) for how the Playwright `Browser`/`BrowserContext`/`Page` are already wired into the Cucumber `World`
- Existing step definitions for reusable steps before writing new, near-duplicate ones

Match what's already there. Introducing a second style of World setup or a parallel set of near-identical steps is worse than slightly awkward reuse of what exists.

### 3. Write the feature file
- One `Feature:` per file, named after the capability, not the ticket number.
- If the feature has multiple distinct business rules, group their scenarios under `Rule:` blocks rather than one flat list — see above.
- One behavior per `Scenario:`/`Example:`. If a scenario needs "and then, separately, verify this other unrelated thing," split it.
- Use `Given` for setup/context, `When` for the action under test (ideally exactly one per scenario), `Then` for observable outcomes. `And`/`But`/`*` continue the previous keyword's intent — see above for when `*` helps.
- Use `Scenario Outline` + `Examples` when the same behavior needs to be checked across a small table of inputs — not as a way to cram unrelated scenarios together.
- Use `Background` only for setup shared by *every* scenario in the file (or in the `Rule`, if scoped to one); if only some scenarios need it, it belongs in `Given` steps instead.
- Tag deliberately (`@smoke`, `@wip`, `@ticket-06`) matching whatever tag vocabulary the project already uses — don't invent a new tagging scheme per feature.

### 4. Write step definitions that stay thin
- Prefer Cucumber expressions (`{string}`, `{int}`, `{word}`) over regex for readability; use regex only when a Cucumber expression genuinely can't express the match.
- A step definition's body should mostly be a call into a page object that wraps Playwright locators/actions — not a pile of raw Playwright calls inline, and never a call into the application's own source code. "Thin" means thin *Playwright* wrapping, not a shortcut around the browser.
- Reuse steps aggressively. Before adding a new step, search for one that already says approximately the same thing with a parameter.
- Keep step definitions independent of each other's internal state except through the `World` — no relying on execution order beyond what Gherkin already implies (Given → When → Then).

### 5. Wire Playwright in correctly
- Create the `Browser` once per test run (`BeforeAll`), a fresh `BrowserContext` (and `Page`) per scenario (`Before`/`After`) so scenarios don't leak state into each other.
- Use role- and test-id-based locators (`page.getByRole(...)`, `page.getByTestId(...)`, `page.getByLabel(...)`) over CSS/XPath selectors — they survive markup changes and read closer to user intent.
- Never add manual `page.waitForTimeout(...)` sleeps. Rely on Playwright's auto-waiting, or wait on a specific condition (`expect(locator).toBeVisible()`, `page.waitForResponse(...)`) if auto-waiting genuinely isn't enough.
- On failure, capture a screenshot and/or trace in an `After` hook keyed to the scenario's result, if the project doesn't already do this — it's what makes a failing BDD run debuggable later instead of just "step 4 failed."

### 6. Verify
Run the new/changed scenarios in isolation before assuming they're done:
```
npx cucumber-js features/path/to.feature
```
Confirm they fail for the right reason against unimplemented behavior (if written before the implementation) or pass against the finished implementation, and that they don't leave the run in a different state than they found it (no leaked browser contexts, no test data that breaks a later scenario).

## Anti-patterns to avoid

- **UI mechanics in the feature file** — clicks, CSS classes, field IDs. Push these into step definitions.
- **Reaching into the application to bypass the UI** — importing app modules, calling internal functions, hitting the database or an internal API directly from a step definition. Drive it through the page, every time.
- **Asserting against application/store/database state instead of what's rendered** — a `Then` step should read the page, not the app's internals.
- **One giant scenario covering many behaviors** — split by outcome, not by convenience.
- **Steps that duplicate existing steps with slightly different wording** — search first, reuse, parameterize.
- **Shared mutable page/context across scenarios** — causes order-dependent flakiness; give each scenario its own context.
- **Hard-coded waits (`waitForTimeout`)** — masks race conditions instead of fixing them, and makes the suite slow.
- **Asserting on incidental detail** (exact pixel position, CSS class names, whitespace) instead of the behavior the ticket actually cares about.
- **Regex step definitions where a Cucumber expression would do** — harder to read, harder to reuse.
- **A test runner other than Playwright** — no Puppeteer, Selenium, jsdom, or raw HTTP clients standing in as the driver.

## Output format when writing new scenarios/steps into an implementation

When this is used as part of implementing a ticket, produce:
1. The `.feature` file (new or diffed) with the scenario(s) covering the ticket's acceptance criteria.
2. Any new or updated step definitions, reusing existing ones wherever the wording already matches.
3. A one-line note on any `World`/hook changes made, if the scenario needed new Playwright setup that didn't already exist.
4. The exact command used to verify the scenario runs (and its result), not just an assertion that it "should work."

