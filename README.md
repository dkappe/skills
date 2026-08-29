# skills

My agent skills.

Inspired by Matt Pocock.

### smallify

Turns a ticket into a plan a small, local, or otherwise weaker LLM can execute without having to think too hard.

Small models don't reason well about ambiguity — they can't reliably fill in gaps, hold a multi-step plan in working memory, or explore a codebase to find "the right place" for a change. `smallify` does that work up front: it investigates the codebase, resolves any ambiguity in the ticket, and rewrites it into small, ordered, independently verifiable steps. Each step names the exact file and location to change and describes the required behavior precisely — without writing the code itself, so the small model still does the implementation, just with no guesswork about what or where.

The skill only rewrites the ticket. It never touches the codebase directly.
