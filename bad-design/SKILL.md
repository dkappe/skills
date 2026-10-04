---
name: bad-design
description: Review an app's UI and UX from screenshots, the way a senior product designer would review a PR. Use when the user asks for a design review, UX review, visual QA, or critique of screens, or hands over screenshots or a URL/route (it can generate screenshots itself with Playwright across widths, themes, and states) and asks what's wrong or how to improve them. Reads the related issue(s) and ADRs as the intent and constraints to review against. Produces a findings report with severity, evidence, fix hints (no code), and a score out of 10 where above 8.5 passes; asks the user when a finding hinges on unstated intent.
---

# bad-design — design review from screenshots

You are reviewing what the user will actually see. Screenshots are the primary evidence; the issue says what the screen is *for*; the ADRs say what is already decided. The output is a findings report that a developer or a smaller model can act on — like a good code review, but for the interface.

## Iron rules

1. **Review only what you have seen.** Open every screenshot with your file/image reading tool before writing a single finding about it. If you cannot view images (non-vision model, unreadable file), stop and say so — never review a screen from its filename, the code, or a description.
2. **Every finding has evidence.** Cite the screenshot file and where on it (region + element, e.g. "`checkout-375.png`, bottom sticky bar, the 'Pay' button"). A finding you can't point at is an opinion; put it under Taste or drop it.
3. **Don't guess what a still image can't show.** Hover, focus order, motion, timing, keyboard behavior, screen-reader output, and exact colors are not visible (or not reliably visible) in a screenshot. A single hover or focus state you deliberately captured (via `steps`) can be reviewed as what it is: one moment, not the behavior. List them under **Needs live check** with what to check — don't report them as defects.
4. **ADRs are settled.** Don't re-litigate a decision an ADR records. If a screen contradicts an ADR, that's a finding. If you think the ADR itself is wrong, raise it as a question (see "Questions"), never as a finding.
5. **Fixes are hints, not code.** Describe the fix as intent + design-system names (token, component, spacing step, type style). No CSS/JSX blocks. The implementer writes the code.
6. **Separate violations from taste.** A violation breaks something checkable (the issue's acceptance criteria, an ADR, the design system, WCAG, a platform convention, internal consistency). Taste is your preference. Both are welcome; they are never mixed in the same list.
7. **The score is computed from the findings, never felt.** Settle the findings first, then derive the score with the rubric in Step 5. Never adjust a finding's severity to reach a score you had in mind.

## Step 1 — Gather inputs

**Screenshots.** Accept any of: image paths, a folder, images attached in chat, or a URL/route plus instructions to capture. If you only get one viewport or one state, work with it and note the gaps in the report's Coverage section — don't stall.

**Generating screenshots.** When the user gives a URL or route instead of images, asks you to capture, or the screenshots you have miss states or widths the issue needs, generate them with the bundled script `scripts/capture.mjs` (Playwright, Node 18+). It captures every screen × state × theme × width, names files `<screen>-<state>-<theme>-<width>.png` (plus `-full.png` when the page is taller than the viewport), and writes a `manifest.json` recording the URL, console errors, and failed requests for each capture.

1. **Check prerequisites.** The app must be running and reachable. If it isn't, ask the user for the URL or how they start it; don't guess a dev command. Playwright must be installed in the project; if the script reports it missing, ask before running `npm i -D playwright && npx playwright install chromium`.
2. **Write the config** as `bad-design.screens.json` at the repo root (copy the shape of `assets/screens.example.json`). Derive the screens and states from the issue: every state the issue or its acceptance criteria imply gets an entry. Default set: widths 375 / 768 / 1440, light and dark if the app has both, and states default, empty, loading, error, long content, and any success/validation state. Produce data states with `mocks` (`json` for fixed data, `status` for errors, `hang: true` to hold a loading state); produce interaction states with `steps` (`fill`, `click`, `press`, `hover`, `focus`, `waitFor`, `scroll`, `reload`, `setLocalStorage`). Mask anything that changes per run (timestamps, avatars) with `mask`. If the app themes by class or setting rather than `prefers-color-scheme`, put the switch in `themeSteps`. If an existing config is there, reuse and extend it rather than replacing it.
3. **Auth.** For logged-in screens, use a Playwright storage-state file (`"storageState"`). Never ask for or type credentials yourself; ask the user to create the file, e.g. `npx playwright codegen --save-storage=.auth/user.json <url>`, and make sure it's gitignored.
4. **Dry-run, then capture:** `node <skill-dir>/scripts/capture.mjs --config bad-design.screens.json --dry-run` to confirm the list, then without `--dry-run`. Output defaults to `design-reviews/shots/<date>/`; `--only <screen>` re-captures one screen. Run it from the repo root so Playwright resolves from the project.
5. **Use the manifest.** It drives Coverage and the Provisional flag. A failed capture (exit code 2, `ok: false`, `-FAILED.png` alongside) is a coverage gap or a broken config. Fix the config and re-run once; if it still fails, list it under Not covered. A failed capture is never a design finding, unless the screenshot itself shows the app broken (blank screen, crash page). Console errors in the manifest are supporting evidence for such findings, not findings on their own.

Then open the screenshots and review them exactly as if the user had supplied them: Iron rule 1 applies to generated images too. With a 3 × 2 × 6 matrix you'll get 36+ images, so open the 1440 light set of every state first, then the other widths and themes for responsive, theme, and consistency passes. You don't need to view every combination in full if they match, but say in Coverage which ones you only spot-checked.

If neither the script nor any other browser tool can run, ask the user for screenshots and list exactly which ones you need, by the same file names.

**Issue(s).** Read the issue(s) the screens implement — local markdown files, or via the tracker CLI if one is configured (e.g. `gh issue view <n>`). Extract: the user goal, acceptance criteria, and any explicit UX requirements. If there's no issue, ask for one sentence of intent ("what is this screen for, and for whom?") in your first question round.

**ADRs.** Find ADRs that touch these screens (search the ADR directory for the feature, component, and screen names; check any the issue links). Extract the decisions as a short list of constraints you'll review against.

**Design system.** If the repo has tokens, a component library, a style guide, or a DESIGN.md, skim it so fix hints can use real names. If there's none, say so in Coverage and review for internal consistency instead.

## Step 2 — Look before judging

For each screenshot, before any critique, write yourself a one-paragraph plain description: what the screen is, the primary action, what the eye lands on first, second, third. If the first thing the eye lands on is not the primary action or the most important information, that's usually your top finding.

Then compare screens against each other: the same component should look and behave the same everywhere. Cross-screen inconsistency is one of the most reliable things a screenshot review catches.

## Step 3 — Review passes

Work through these in order. Skip a pass only if it doesn't apply, and say which you skipped.

1. **Intent** — Does the screen let the user do what the issue says, and does it meet each acceptance criterion that's visible? Does it honor every relevant ADR? Is anything required missing entirely?
2. **Hierarchy & layout** — Primary action obvious; clear grouping; alignment to a consistent grid; spacing from a consistent scale (look for off-scale gaps and uneven padding); nothing orphaned or cramped.
3. **Typography** — Number of sizes/weights in use (too many is a finding); readable body size; line length; truncation and wrapping; heading levels that match importance.
4. **Color & contrast** — Color used consistently for meaning (one "danger", one "primary"); state conveyed by more than color alone. For contrast: if you can run a script, sample foreground/background pixels from the image and compute the WCAG ratio; otherwise mark the finding *estimated* and move exact measurement to Needs live check. Targets: 4.5:1 body text, 3:1 large text and UI component boundaries.
5. **States** — Empty, loading, error, overflow, first-run, permission-denied, offline: which are shown, which are missing, and whether the shown ones tell the user what to do next.
6. **Copy** — Labels say what happens ("Delete project", not "OK"); consistent terminology across screens and with the issue/ADR vocabulary; error messages explain cause and recovery; no placeholder or lorem text.
7. **Responsive** — Per width: reflow vs. squeeze, hidden-but-needed content, horizontal scroll, touch targets (visible target at least 24×24 CSS px, 44×44 recommended for primary touch actions), sticky elements eating the viewport.
8. **Accessibility (visible cues)** — Visible labels on inputs (not placeholder-only), focus indicator if a focused state was captured, icon-only buttons, text in images, reading order implied by layout. Everything not visible goes to Needs live check.
9. **Consistency & polish** — Against the design system and across screens; icon style mix; radius/shadow/border drift; generic "AI default" look (purple gradient, identical card grids, stock font) when the product has its own identity.

## Step 4 — Questions (only when intent is unclear)

Some findings depend on a decision nobody has written down (is this screen for power users or first-timers? is density or scannability the goal?). Don't guess and don't pad the report with both readings. Ask, batched in one round, in this format:

    ❓ Q<N> — <short title>
    Context: <what you saw, citing the screenshot, and why it forces a choice>
    Options:
      A. <option> — <what it means for the design; main trade-off>
      B. <option> — <what it means for the design; main trade-off>
    ➡️ Recommendation: <letter> — <reasoning grounded in the issue/ADRs/screens>
    If unanswered: I review against <letter> and note it as an assumption.

Only ask what changes findings. Things you can read from the issue, ADRs, or design system are not questions. If a question is really "how should this feel", recommend a prototype of 2–3 variants instead of choosing. If an answer is a lasting decision, suggest recording it as a new ADR.

## Step 5 — Score

The score answers one question: is this shippable as-is, apart from polish? **Passing is strictly above 8.5** (8.5 itself fails).

**1. Score each dimension 0–10** from its findings, using these anchors:

| Dimension score | Findings in that dimension |
|---|---|
| 10 | none |
| 9 | nits only |
| 8 | one or two minors |
| 7 | three or more minors |
| 6 | one major |
| 4–5 | two or more majors |
| 0–3 | a blocker, or the dimension is fundamentally broken or missing |

Pick within a range by how much of the screen the problems cover. A problem that spans dimensions counts in the one it hurts most, never twice.

**2. Weight and average** over the dimensions you could assess:

| Dimension (review pass) | Weight |
|---|---|
| Intent (issue + ADRs) | 20 |
| Hierarchy & layout | 15 |
| Typography | 10 |
| Color & contrast | 10 |
| States | 10 |
| Copy | 10 |
| Responsive | 10 |
| Accessibility (visible cues) | 10 |
| Consistency & polish | 5 |

Weighted score = sum(score × weight) / sum(weights of assessed dimensions), rounded to one decimal.

**3. Apply caps** — the lowest applicable cap wins:
- any **Blocker** → capped at **6.0**;
- any **Major** → capped at **8.4** (a major is real user friction, so it can't pass);
- **Intent** not assessable (no issue and no answer to the intent question) → no score; report **Unscored** and say what's needed.

**4. Coverage flag.** If the assessed dimensions carry less than 70 of the 100 weight (e.g. only one width, no states captured), mark the score **Provisional** and list what to capture to finalize it. A dimension that can't be judged from the screenshots is excluded, not given a 10.

**What doesn't affect the score:** Taste items, and Needs-live-check items (they're unknowns, not defects). When they're verified live, re-score.

**Re-reviews:** if an earlier report exists for the same screens, show the previous score and the delta, and mark each earlier finding fixed / still open / regressed. If a `bad-design.screens.json` exists, re-capture with it first so before and after cover the same matrix.

## Step 6 — Write the report

Write the report to a file (default `design-reviews/<yyyy-mm-dd>-<screen-or-issue>.md`, or wherever the repo keeps reviews), and post a short summary in chat: the score and PASS/FAIL, counts by severity, and the top three findings. If the user prefers, post the report as an issue comment instead.

Severity:
- **Blocker** — the user can't complete the issue's goal, an acceptance criterion or ADR is violated, or a clear accessibility failure.
- **Major** — the goal is achievable but with real friction, confusion, or a likely error.
- **Minor** — noticeable inconsistency or polish problem.
- **Nit** — small, optional.

Report format:

```markdown
# Design review: <screen / feature> (<issue ref>)

## Summary
**Score: X.X / 10 — PASS | FAIL** <(Provisional) if flagged; "cap: blocker/major" if a cap applied; "prev Y.Y, ΔZ" on re-review>
<2–4 sentences: overall verdict, the one thing to fix first, and what would lift it past 8.5.>
Blockers: N · Major: N · Minor: N · Nits: N

## Score breakdown
| Dimension | Weight | Score | Driven by |
|---|---|---|---|
| Intent | 20 | 9 | 1 nit |
| … | … | … | … |
| **Weighted** | | **X.X** | cap applied: <none / blocker 6.0 / major 8.4> |

## Coverage
Screens reviewed: <files, or the shots folder + manifest>. Widths/themes/states covered: <…>. Spot-checked only: <…>.
Not covered: <missing states/widths>. Inputs used: <issue, ADR-00xx, design system or "none found">.
Assumptions: <any unanswered-question defaults>.

## Findings
### [Blocker] <title>
- Where: `<file>` — <region, element>
- What: <what is wrong, observably>
- Why it matters: <user impact; the criterion/ADR/guideline it breaks>
- Fix hint: <intent + token/component names; no code>

<…ordered by severity, then by screen…>

## Needs live check
- <what to verify in the running app, and how (keyboard, screen reader, hover, contrast tool)>

## Taste (optional, non-blocking)
- <preference, with a one-line reason>

## What works
- <1–3 things to keep, so fixes don't regress them>
```

## Done means

- [ ] Every screenshot was opened and viewed; none was reviewed from its name or the code. Generated sets: every state viewed at least once, spot-checks named in Coverage.
- [ ] If screenshots were generated: the config is saved at `bad-design.screens.json` for re-reviews, and every failed capture is either fixed or listed under Not covered.
- [ ] Every finding cites a file and a location, has a severity, and has a fix hint with no code.
- [ ] Every acceptance criterion from the issue and every relevant ADR was checked, or listed as not checkable from the screenshots.
- [ ] Nothing a still image can't show was reported as a defect; those items are in Needs live check.
- [ ] Violations and taste are in separate sections.
- [ ] The score was computed from the findings with the rubric: every dimension scored or marked excluded, weights applied, caps applied, Provisional flag checked. PASS only if strictly above 8.5.
- [ ] The report file exists and the chat reply is a short summary (score, verdict, counts, top three) pointing to it.
