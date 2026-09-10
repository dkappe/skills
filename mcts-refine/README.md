# MCTS Refinement Skill for OpenCode

Monte Carlo Tree Search (MCTS) engine featuring **PUCT** (Polynomial Upper Confidence Trees) for stateful artifact refinement (text, code, prompts, image generation latents/diffs). Moves are proposed in full batches per node — like an AlphaZero policy head — with priors normalized to sum to 1.0, and expanded lazily (state + value generated only once PUCT actually selects a move).

The harness is intentionally **dumb**: it never opens or renders artifact content — it only copies artifact paths (files or directories) into its own cache and hands back references. The driving LLM agent reads/writes artifact content itself with its own tools; the Python only does tree bookkeeping.

## Search stats on every call (lc0-style)

Every command that changes or reads the tree (`init`, `step`, `propose`, `record`, `best`) includes a stats block alongside its own payload:

```json
{
  "iterations_done": 37, "target_iterations": 100, "iterations_remaining": 63,
  "total_nodes": 52, "tree_max_depth": 6,
  "root_children": [
    {"action_id": "act_2", "desc": "Add concrete benchmarks", "prior": 0.40, "risk": "bold",
     "expanded": true, "child_id": "n_5", "visits": 18, "q_value": 0.71,
     "subtree_nodes": 21, "subtree_depth": 5},
    {"action_id": "act_1", "desc": "Simplify introduction", "prior": 0.30, "risk": "safe",
     "expanded": true, "child_id": "n_2", "visits": 12, "q_value": 0.65,
     "subtree_nodes": 14, "subtree_depth": 4},
    {"action_id": "act_4", "desc": "Rewrite as an interactive FAQ", "prior": 0.15, "risk": "wild",
     "expanded": false, "child_id": null, "visits": 0, "q_value": null,
     "subtree_nodes": 0, "subtree_depth": 0}
  ]
}
```

`root_children` is the root's candidate moves ranked by **visit count** (tie-break Q, then prior), capped to the **top 3** during the search; unexpanded stubs appear with zero visits so the policy priors stay visible. In the final `best` output the cap is lifted to all root moves.

During the search the agent emits nothing to the chat. Instead, each iteration appends one compact lc0-`info` stats line to **`refine.md`** in the search's working directory — the run's progress log, created at `init`, holding one stats line per iteration plus the final summary. No shell commands, no JSON dumps, no move batches, no artifact content, no other evidence in chat: the agent parses the harness JSON silently and logs only the stats lines. After the search completes, the **top three concepts are saved as `one`, `two`, `three`** — named appropriately to the artifact (e.g. `one.md`/`two.md`/`three.md` for a markdown input, `one/`/`two/`/`three/` for a directory), `one` being the winner — and the **original artifact is left unmodified**. `refine.md` gets the final ranked summary (root moves with visits, Q, node counts, depths, and the three delivered paths); the chat carries nothing — read the log, read the files.

## Architecture

- **`skill.json`**: OpenCode skill definition with metadata and tool schema.
- **`engine.py`**: Clean, JSON-serializable PUCT engine with node-level statistics. `select()` runs PUCT over a node's full action set — expanded children and unexpanded ("stub") proposed moves alike (stubs use First Play Urgency: q=0, visits=0) — so it may return a pending action to realize, a signal that a node needs moves proposed, or a dead end.
- **`run_mcts.py`**: CLI harness designed for LLM agents to execute `init`, `step`, `propose`, `record`, and `best` operations.
- **JSON state & Artifact Cache**: Metadata is stored in `.mcts_tree.json` and artifact states are decoupled into `.mcts_artifacts/` (opaque copies of file/directory paths — never read by the harness itself) to keep tree operations fast and light.

## Usage Walkthrough

1. **Initialize the search tree** with the iteration budget, target batch
   size/wildness, and the root's first batch of candidate moves (priors
   should sum to 1.0 — the harness normalizes and warns if they don't; each
   move can carry a `risk` of `safe`/`bold`/`wild`). `--state-file` is
   **required** and must point to a real file (single artifact) or directory
   (multi-file/project artifact) on disk — inline text is not accepted as the
   artifact to refine:
   ```bash
   python run_mcts.py init --state-file draft.txt --iterations 100 \
     --batch-size 4 --wildness 0.25 \
     --moves '[{"desc":"Simplify introduction","prior":0.5,"risk":"safe"},{"desc":"Add concrete benchmarks","prior":0.3,"risk":"bold"},{"desc":"Rewrite as an interactive FAQ","prior":0.2,"risk":"wild"}]'

   # or, for a directory/project artifact:
   python run_mcts.py init --state-file ./my-project --iterations 100 \
     --moves '[{"desc":"...","prior":0.6,"risk":"bold"},{"desc":"...","prior":0.4,"risk":"wild"}]'
   ```
   The response's `artifact_kind` (`"file"` or `"directory"`) confirms what
   was registered. `init` **refuses to run if a tree already exists** in the
   CWD (unless `--force-restart` is passed) — there is exactly one tree and
   one root per directory; to continue an existing search, call `step` instead
   of re-initializing. `--batch-size` (default `4`) and `--wildness` (default
   `0.25`, the target fraction of each batch tagged `"wild"`) are reminders
   echoed back in every `step`/`propose`/`record` response as
   `target_batch_size`/`target_wildness` — the harness warns if a 3+ move
   batch has zero `"wild"` entries while `wildness > 0`.

2. **Select a node/move to work on**:
   ```bash
   python run_mcts.py step
   ```
   If `status` is `ready_for_moves`, the target node has no candidate moves
   yet — propose a batch for it first:
   ```bash
   python run_mcts.py propose --node-id "n_0" \
     --moves '[{"desc":"Restructure for clarity","prior":0.45,"risk":"safe"},{"desc":"Cut length","prior":0.35,"risk":"bold"},{"desc":"Invert the argument entirely","prior":0.2,"risk":"wild"}]'
   ```
   If `status` is `ready_for_eval`, PUCT already picked a specific
   `target_action_id` with a known description/prior/risk — realize that move.
   The `state_ref` it reports is a path (`.mcts_artifacts/n_X.state`) — the
   agent reads it with its own tools; the harness does not embed content.

3. **Record the realized move + critic evaluation** — first write the edited
   artifact to disk yourself (a file, or a whole directory copy for directory
   artifacts), then point `record` at that path (optionally proposing the new
   child's own next batch of moves in the same call):
   ```bash
   python run_mcts.py record \
     --node-id "n_0" \
     --action-id "act_1" \
     --new-state-path ./edited-draft.txt \
     --value 0.85 \
     --moves '[{"desc":"...","prior":0.6,"risk":"bold"},{"desc":"...","prior":0.4,"risk":"wild"}]'
   ```
   `--new-state-path` is required and takes a real file or directory path
   (matching the root artifact's kind) — there is no inline-text option; the
   harness just copies what you point it at.

4. **(Optional, mid-run) Snapshot the current best**: `best` only reads tree
   bookkeeping, so it can be run before the budget is exhausted too — e.g. if
   asked "what's the best so far" or "update best.md". Run
   `python run_mcts.py best --top 1` and copy the rank-1 concept's
   `leaf_state_ref` to a single overwritable `best.<ext>` file (or `best/`
   for a directory artifact) next to the original. This does not end the
   search, doesn't touch `.mcts_tree.json`/`.mcts_artifacts/`, and isn't the
   final `one`/`two`/`three` delivery — the loop just resumes on the next
   `step`. Note in your reply that it reflects the search so far and may
   change with more iterations.

5. **Extract the top concepts** (after the full iteration budget has been run
   — each `step`/`record` call reports `iterations_done`,
   `iterations_remaining`, `total_nodes`, and `tree_max_depth` so progress is
   trackable):
   ```bash
   python run_mcts.py best            # top 3 concepts by default
   python run_mcts.py best --top 5    # or however many you want
   ```
   A "concept" is one of the root's first moves (its most distinct strategic
   directions). For each concept, `best` walks the most-visited (robust-child)
   path from the root through that concept and returns:
   - `rank` — 1 is the strongest concept
   - `concept` — the first move's description
   - `final_q_value` / `final_visits` / `depth` — leaf stats behind that ranking
   - `subtree_nodes` / `subtree_depth` — the node count and the deepest chain
     under that root move (report these per root move in the final summary)
   - `leaf_state_ref` — path to that concept's refined artifact on disk
   - `trajectory` — the full node/action chain from ROOT to the leaf

   Ranking is by **leaf visit count** (robust-child rule: how much of the
   search's total attention this concept's best line attracted), tie-broken by
   Q-value. Visit count is preferred over raw Q because a single expansion
   with one generous critic score should not outrank a direction the search
   kept returning to. The output also lists **all** root moves (uncapped
   `root_children`, ranked by visits with subtree stats). Deliver the top
   three concepts as `one`/`two`/`three`, named appropriately to the
   artifact (`one.md`… for a file with its original extension, `one/`… for a
   directory), `one` = the winner, and leave the original artifact
   unmodified. Append the final ranked summary to `refine.md`; the chat
   carries nothing — never pasted content.

## Prompt options

Everything a user (or the driving prompt) can tune, and where it lands:

| Option | Type / range | Default | Meaning |
| ------ | ------------ | ------- | ------- |
| **Artifact** | file or directory path | required | The thing to refine, passed as a path (`--state-file` at init; `--new-state-path` at record). Inline text is never accepted — write it to a scratch file first. |
| **Objective / rubric** | free text | required | What the critic scores every state against; sub-criteria are averaged into one `[0,1]` value. |
| **Iterations** | integer | `100` | Total expansion budget (`--iterations`). Each realized move = one iteration; proposing moves is free. Keep looping until `iterations_remaining` hits 0. |
| **Batch size** | integer | `4` | Target moves per batch (`--batch-size`), echoed as `target_batch_size`. A reminder only — the agent generates each batch. |
| **Wildness** | float `[0,1]` | `0.25` | Target fraction of each batch tagged `"risk":"wild"` (`--wildness`), echoed as `target_wildness`. The harness warns when a 3+ move batch has zero wild entries while this is > 0. |
| **Risk tags** | `safe` / `bold` / `wild` | `bold` | Per-move exploration character. `safe` = incremental, low blast radius; `bold` = real structural change; `wild` = long-shot (break the format, invert an assumption). |
| **Priors** | floats summing to 1.0 | — | Policy distribution over sibling moves; normalized-and-warned if they don't sum to 1.0. |
| **Critic values** | float `[0,1]` | — | Post-hoc rubric score per recorded state (`--value`). Independent of priors; consistency across the run is what keeps Q-values meaningful. |
| **Top concepts** | integer | `3` | How many root-level directions `best` returns (`--top`), each as a robust-child trajectory. |
| **c_puct** | float | `1.414` | PUCT exploration constant (in `engine.py`): higher favors high-prior/unvisited branches, lower favors exploitation of proven lines. |
| **max_depth** | integer | `0` (unlimited) | Longest single refinement chain (in `engine.py`); set a positive cap only if deep chains are undesirable. |
| **widening_c / widening_alpha** | floats | `1.5` / `0.5` | Legacy progressive-widening knobs from the one-move-at-a-time design; unused by the current batch-based `select()`, kept only for backward-compatible tree loading. |
| **Reporting style** | stats log | `refine.md` | The chat stays empty during the loop; each iteration appends one lc0-style stats line to `refine.md`. At the end, the top three concepts are saved as `one`/`two`/`three` (named to the artifact), the original stays unmodified, and `refine.md` gets the ranked root moves with node counts and depths plus the three paths. |
| **Force restart** | flag | off | `init --force-restart` deliberately discards the existing tree; never used to "continue" — call `step` instead. |

Prompting examples that set these knobs live in the Worked Examples below
(e.g. "40 iterations, medium exploration" ≈ wildness 0.25–0.35; "low
exploration, no speculative rewrites" ≈ wildness ≤ 0.15).

## Worked Examples

The following sketches show how the same init/step/propose/record/best cycle
adapts to different artifact types. You never run the harness yourself — you
just describe the task in a prompt to opencode and the agent drives the whole
cycle (it spins up a dedicated working directory per search — one tree per
CWD — and does all content reading and writing with its own tools between
harness calls). What matters from you is the objective, the rubric, and any
budget/exploration preferences.

### Example 1: Refining an essay (`essay.md`)

Goal: sharpen a mediocre essay against a rubric — clear thesis, concrete
evidence, tight prose. Text is malleable, so medium exploration works well.

```text
Refine essay.md with MCTS against this rubric: a clear falsifiable thesis
at the top, concrete evidence in every section, tight prose.
40 iterations, medium exploration.
```

The agent will propose batches mixing safe moves (sharpen/cut/reorder
arguments, tighten prose) with bold ones (add evidence or counterexamples)
and the occasional wild restructure (e.g. thesis/antithesis/synthesis). The
critic values track the rubric, not the priors — a "wild" restructure scoring
0.8 is exactly the kind of surprise the search exists to find. When the
budget is spent, it reports back the top-ranked concepts and their refined
essays.

### Example 2: Writing a sonnet about AI from scratch

Goal: a Shakespearean sonnet (14 lines, ABAB CDCD EFEF GG, iambic pentameter).
Since the artifact must be a path, you paste your first rough attempt (even a
single couplet) and the agent starts from there.

```text
Write a Shakespearean sonnet about AI with MCTS. Start from this couplet:

    The machines we taught to speak now speak of us.

30 iterations, and push exploration higher than usual — formal constraints
make incremental edits plateau. Score against: form (meter+rhyme) 40%,
imagery freshness 35%, thematic depth 25%.
```

The agent writes the seed to a file itself, then explores: completing
quatrains, moving the volta, even inverting the POV mid-search. Each state is
the *complete current sonnet*, so a move can be as small as fixing one line's
meter — the state just has to always contain all 14 lines. Poetry rewards
that higher exploration (0.3–0.4): a POV or volta inversion can break a
plateau that incremental polish never would.

### Example 3: Refining a proof about infinite prime pairs (`proof.md`)

Goal: tighten a draft argument about infinitely many prime pairs (twin-prime
style) toward rigor. Math needs the most careful critic scoring — an
emotive-sounding paragraph can score 0.9, but a proof step with a hidden
uniformity assumption is a 0.2 no matter how good the prose looks. Keep
exploration low; speculative math usually wastes iterations.

```text
Refine proof.md with MCTS toward rigor. It argues for infinitely many prime
pairs (twin-prime style). Score moves against: logical validity (dominant
weight), completeness of cases, clarity of exposition. Be a harsh critic —
a move that silently strengthens an unstated hypothesis must score LOW even
if the resulting text reads cleaner.
50 iterations, low exploration, no speculative rewrites.
```

The agent will weight its scoring like `value = 0.7*(rigor) + 0.2*(case
completeness) + 0.1*(clarity)` — an unproven "standard" step caps the whole
state's value around 0.5 regardless of polish, so the search grinds toward
lemmas and explicit epsilon-N definitions rather than prettier prose.

### Example 4: Refining a directory (HTML/CSS/assets) toward an AAA web design

Goal: turn a plain multi-page site into a polished AAA-game-quality design.
The artifact is a directory, so every state is a full directory copy — the
agent edits a copy of the tree per move. Structure changes (new files,
renamed assets) are normal moves here.

```text
Refine the site in ./site/ with MCTS into a AAA-game-quality web design:
design-token system, layered gradients and glass cards, scroll-driven
reveals, consistent nav/footer across all pages. 60 iterations, moderate
exploration. Judge each state as a coherent whole — visual hierarchy,
cross-page consistency, performance sanity — not as isolated pages.
```

The agent reads the whole state tree each round, edits a copy, and scores it
as a unit; "added `tokens.css` defining the spacing scale" shows up in the
trajectory like a changelog entry. Directory tips: keep the iteration budget
moderate (directories multiply the content regenerated per move), and treat
"added a file" as part of the move description.
