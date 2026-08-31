---
name: gherkin-eyeball
description: Run Gherkin/Cucumber-js/Playwright scenarios, capture screenshots at the checkpoints that matter, and actually look at them to verify the UI genuinely displays what the scenario claims — catching visual bugs (clipped content, elements covered by an overlay, text rendered unreadable against its background, content scrolled off-screen, broken layout) that DOM-based assertions like toBeVisible() can pass right through. Use this whenever the user asks to visually verify, screenshot-check, or confirm BDD/Cucumber/Playwright scenarios actually render correctly, not just that their assertions pass. Ad hoc and read-mostly, like gherkin-critic — it writes screenshots and one report, runs scenarios to produce them, and removes any temporary capture instrumentation afterward — it doesn't add permanent visual-regression infrastructure or baseline snapshots to the suite unless the user separately asks for that.
---

# Gherkin Eyeball

Look at what the tests actually rendered — DOM assertions and visual reality aren't the same thing.

## Why this exists

`expect(locator).toBeVisible()` checks that an element is attached, has non-zero size, and isn't `visibility:hidden`/`display:none`. That's it. It says nothing about whether the element is clipped by `overflow:hidden` on a parent, covered by a modal or a z-index conflict, scrolled outside the viewport, or rendered in white text on a white background. A scenario can pass every assertion in gherkin-genius's book and still be showing a real user something broken. The only way to catch that class of bug is to actually look at the pixels.

## Relationship to gherkin-genius and gherkin-critic

gherkin-genius writes the scenarios and step definitions; gherkin-critic statically audits them for structure and UI-layer violations. Neither one looks at a rendered pixel — they both work at the level of code and DOM assertions. gherkin-eyeball is the dynamic complement: it runs scenarios, captures what actually appeared on screen, and judges that against what the scenario's `Then` step claims. Running gherkin-critic first (structure/UI-layer audit) and gherkin-eyeball second (does it actually look right) gives fuller coverage than either alone.

## Hard constraint: ad hoc and read-mostly

- **Writes**: the screenshot image files it captures, and exactly one markdown report. Nothing else.
- **Runs scenarios** — unlike gherkin-critic, this skill's whole point requires actually executing the suite (or the in-scope subset of it) to produce real screenshots. Flag to the user before running anything that could have side effects (seeded test data, real emails/webhooks, anything beyond a local/test environment) so they can confirm first.
- **May add temporary capture instrumentation** (e.g. a small custom Cucumber formatter or hook file dedicated to screenshotting) if the project doesn't already have a way to capture mid-run screenshots — but only as a new, self-contained file that doesn't touch any existing `.feature`, step definition, or support file, and it's **removed immediately after the run**, pass or fail, so the repository is left exactly as it was found.
- **Never** edits, fixes, or permanently modifies any existing test file, and never commits baseline/golden images or wires in durable visual-regression tooling (Playwright's `toHaveScreenshot`, committed snapshots) — that's a deliberately separate, larger piece of infrastructure the user can ask for explicitly if they want it later.
- **Never fixes the underlying rendering bug.** A visual failure found here is almost always an app bug, not a test bug — report it; fixing app CSS/layout code is out of scope for this skill.

## Process

### 1. Establish scope
Which scenarios/features are in question — a specific ticket, a feature area, or everything. If the user pointed at something specific, stay scoped to that.

### 2. Identify visual checkpoints
Not every step needs a screenshot — that's noisy, slow, and defeats the purpose. Focus on `Then` steps (or scenario points the user specifically flags) whose entire claim is something a user would *see*: an error message appearing, a modal opening, a banner showing the right content, a layout rendering as expected. A `Then` step confirming a background state change (an email was queued, a record was created) isn't a visual checkpoint even if it's a valid assertion — skip those.

### 3. Determine how to capture
- If the project already has a screenshot mechanism (many Playwright+Cucumber setups capture on failure via an `After` hook), see if it can be pointed at the in-scope checkpoints for this run rather than only firing on failure — reuse what's there before adding anything new.
- If nothing suitable exists, add a small, self-contained temporary formatter/hook file that captures a screenshot right after each in-scope `Then` step, named so each file is traceable back to its scenario and step (e.g. `checkout--declined-card--payment-is-declined.png`). This file lives outside the project's normal support directory structure or is clearly marked temporary, and does not touch any existing file.
- Wait for the page to actually settle before capturing — network idle, and the specific locator the step cares about visible — a screenshot taken mid-render or mid-transition produces false failures that have nothing to do with a real bug.

### 4. Run the scenarios
Run the in-scope scenarios via cucumber-js with the capture mechanism active. If the run has already-flagged side effects, make sure the user's confirmed before this step.

### 5. Clean up immediately
Remove any temporary instrumentation file added in step 3 right after the run finishes — regardless of whether the run passed, failed, or crashed. The screenshots and the report are the only artifacts that should remain; the test suite itself should show no diff.

### 6. Actually look at each screenshot
View each captured image directly and judge it against the `Then` step's claim. Look specifically for:
- **Readability** — is the relevant text/content actually legible (contrast, not overlapping other elements)?
- **Clipping** — is content cut off by a container's `overflow`, or by the viewport edge?
- **Occlusion** — is the expected content covered by a modal, overlay, sticky header, or another element sitting on top of it?
- **Position** — is the content where a user would actually see it, not scrolled out of view?
- **Content match** — does the screenshot show the specific thing the step describes (the right error message, the right item in a list), not just "something" in the right general area?

### 7. Categorize each checkpoint
- **Pass** — the screenshot genuinely shows what the step claims.
- **Fail** — an assertion may have passed, but the screenshot shows something broken; describe exactly what's wrong and, if apparent, a likely cause (e.g. "message text color matches the background — likely a CSS variable regression," or "modal is rendered behind the page overlay — likely a z-index issue"). This is a signal to report to whoever owns the app code, not something to fix here.
- **Inconclusive** — the screenshot is ambiguous (mid-animation, a loading spinner still showing, timing-dependent) — note why and suggest a re-check rather than guessing.

### 8. Write the report
One markdown file at the path the user specifies (ask if not given, same as gherkin-critic).

## Report format

```markdown
# Visual Verification — [scope]

## Summary
[N] checkpoints captured — [N] pass, [N] fail, [N] inconclusive.
Viewport(s) checked: [e.g. 1280x720 desktop only — note if mobile/other breakpoints weren't covered]

## Failures

### [Scenario] — [Then step text]
**Screenshot:** `path/to/screenshot.png`
**Expected:** [what the step claims should be visible]
**What the screenshot actually shows:** [the specific visual problem]
**Likely cause:** [if apparent — this is almost always an app bug, not a test bug]

### ...

## Passes
- [Scenario] — [step]: matches expectation (`path/to/screenshot.png`)
- ...

## Inconclusive
- [Scenario] — [step]: [why ambiguous, suggested re-check]

## Cleanup
[Confirmation that any temporary capture instrumentation was removed, and the suite shows no diff from before this run.]
```

## Things to watch for
- **Don't screenshot every step.** Only checkpoints whose whole point is something visible — screenshotting everything is noise, not signal.
- **Wait for the page to settle before capturing.** A false failure from bad timing is worse than no check at all — it teaches people to distrust the report.
- **Always clean up instrumentation, even on a crashed run.** The repo should show no diff from the test suite itself when this is done.
- **A visual failure here is an app bug, not a test bug** — report it, don't try to fix the app's CSS/layout as part of this skill.
- **Judge against the specific claim, not general design taste.** Flag whether the step's claimed outcome is genuinely visible and correct — not an unrelated aesthetic opinion about spacing or color choices you happen to disagree with.
- **Say which viewport(s) were actually checked.** One screenshot at one size doesn't cover responsive behavior — don't imply it does.
- **Flag side effects before running the suite**, same as gherkin-critic would flag before running scenarios end-to-end.
