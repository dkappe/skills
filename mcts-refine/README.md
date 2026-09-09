# MCTS Refinement Skill for OpenCode

Monte Carlo Tree Search (MCTS) engine featuring **PUCT** (Polynomial Upper Confidence Trees) for stateful artifact refinement (text, code, prompts, image generation latents/diffs). Moves are proposed in full batches per node — like an AlphaZero policy head — with priors normalized to sum to 1.0, and expanded lazily (state + value generated only once PUCT actually selects a move).

The harness is intentionally **dumb**: it never opens or renders artifact content — it only copies artifact paths (files or directories) into its own cache and hands back references. The driving LLM agent reads/writes artifact content itself with its own tools; the Python only does tree bookkeeping.

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

4. **Extract the top concepts** (after the full iteration budget has been run
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
   - `leaf_state_ref` — path to that concept's refined artifact on disk
   - `trajectory` — the full node/action chain from ROOT to the leaf

   Ranking is by **leaf visit count** (robust-child rule: how much of the
   search's total attention this concept's best line attracted), tie-broken by
   Q-value. Visit count is preferred over raw Q because a single expansion
   with one generous critic score should not outrank a direction the search
   kept returning to. Read each `leaf_state_ref` with your own tools and pick
   the winner — or present several to the user as alternatives.

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
