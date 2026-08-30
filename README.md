# skills

My agent skills.

Inspired by Matt Pocock.

## [smallify](./smallify)

Turns a ticket into a plan a small, local, or otherwise weaker LLM can execute without having to think.

Small models don't reason well about ambiguity — they can't reliably fill in gaps, hold a multi-step plan in working memory, or explore a codebase to find "the right place" for a change. `smallify` does that work up front: it investigates the codebase, resolves any ambiguity in the ticket, and rewrites it into small, ordered, independently verifiable steps. Each step names the exact file and location to change and describes the required behavior precisely — without writing the code itself, so the small model still does the implementation, just with no guesswork about what or where.

The skill only rewrites the ticket. It never touches the codebase directly.

## [gherkin-genius](./gherkin-genius)

Writes and improves Gherkin feature files, Cucumber.js step definitions, and Playwright-driven UI test automation — usable standalone or folded into implementation work (e.g. "implement ticket 06, use gherkin-genius where useful").

Scenarios are written declaratively, describing behavior rather than UI mechanics, and every step is required to actually drive the browser through Playwright — no importing application code, no reaching into the database or an internal API to shortcut past the UI, no assertions against app/store state instead of what's rendered on the page. The skill also checks existing project conventions (tags, `World`/hook setup, existing steps) before adding anything new, so it extends a project's BDD suite instead of forking its style.
