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
adapts to different artifact types. Every command runs in its own dedicated
working directory (one tree per CWD); the agent does all content reading and
writing with its own tools between harness calls.

### Example 1: Refining an essay (`essay.md`)

Goal: sharpen a mediocre essay against a rubric — clear thesis, concrete
evidence, tight prose. Text is malleable, so medium `wildness` works well.

```bash
mkdir run-essay && cd run-essay
python ../run_mcts.py init --state-file ../essay.md --iterations 40 \
  --batch-size 4 --wildness 0.25 \
  --moves '[
    {"desc":"Sharpen thesis to one falsifiable sentence at the top","prior":0.35,"risk":"safe"},
    {"desc":"Add a concrete counterexample paragraph to section 2","prior":0.3,"risk":"bold"},
    {"desc":"Cut the 3 weakest paragraphs and renumber sections","prior":0.2,"risk":"bold"},
    {"desc":"Restructure the whole essay as thesis/antithesis/synthesis","prior":0.15,"risk":"wild"}]'

# Loop (40 times): step -> realize the named move -> record
python ../run_mcts.py step
# status=ready_for_eval, target_action_id=act_1, action_risk=safe
# ... read .mcts_artifacts/n_0.state, apply the move, write ../run-essay-draft.txt ...
python ../run_mcts.py record --node-id n_0 --action-id act_1 \
  --new-state-path ../run-essay-draft.txt --value 0.62 \
  --moves '[{"desc":"Replace anecdote with cited statistic","prior":0.4,"risk":"safe"},
            {"desc":"Tighten every paragraph to <= 4 sentences","prior":0.35,"risk":"bold"},
            {"desc":"Rewrite entire essay in second person","prior":0.25,"risk":"wild"}]'

python ../run_mcts.py best   # last state_ref = refined essay
```

Typical move vocabulary for essays: sharpen/cut/reorder arguments, add
evidence or counterexamples, tighten prose, change register or voice. Values
should track the rubric, not the prior — a "wild" restructure scoring 0.8 is
exactly the kind of surprise the search exists to find.

### Example 2: Writing a sonnet about AI from scratch

Goal: a Shakespearean sonnet (14 lines, ABAB CDCD EFEF GG, iambic pentameter).
The "artifact" starts as a seed file containing your first rough attempt (even
a single couplet — write it to a file first; `--state-file` requires a path).

```bash
echo "The machines we taught to speak now speak of us." > seed.txt
mkdir run-sonnet && cd run-sonnet
python ../run_mcts.py init --state-file ../seed.txt --iterations 30 \
  --batch-size 4 --wildness 0.35 \
  --moves '[
    {"desc":"Complete quatrain 1 with ABAB rhyme (speak/us -> week/becomes)","prior":0.4,"risk":"safe"},
    {"desc":"Draft the volta turn at line 9: from capability to consequence","prior":0.35,"risk":"bold"},
    {"desc":"Abandon the opening line entirely; start from the machine POV","prior":0.25,"risk":"wild"}]'

# Loop (30 times): step -> realize -> record. Score against:
# form (meter+rhyme) 40%, imagery freshness 35%, thematic depth 25%.
python ../run_mcts.py step
# ... write the new full sonnet draft to ../sonnet-draft.txt ...
python ../run_mcts.py record --node-id n_0 --action-id act_2 \
  --new-state-path ../sonnet-draft.txt --value 0.55 \
  --moves '[{"desc":"Fix line 11 meter: and quiet grows -> and quietly it grows","prior":0.45,"risk":"safe"},
            {"desc":"Swap cliche brave-new-world for concrete robotics imagery","prior":0.35,"risk":"bold"},
            {"desc":"Invert the volta: make the machine the anxious one","prior":0.2,"risk":"wild"}]'

python ../run_mcts.py best
```

Note: each state is the *complete current sonnet*, so a move can be as small
as fixing one line's meter — the state just has to always contain all 14
lines. Poetry rewards higher `wildness` (0.3–0.4): formal constraints make
incremental edits plateau quickly, while a POV or volta inversion can break a
plateau.

### Example 3: Refining a proof about infinite prime pairs (`proof.md`)

Goal: tighten a draft argument about infinitely many prime pairs (twin-prime
style) toward rigor. Math needs the most careful critic scoring — an
emotive-sounding paragraph can score 0.9, but a proof step with a hidden
uniformity assumption is a 0.2 no matter how good the prose looks. Keep
`wildness` low; speculative "wild" math usually wastes iterations.

```bash
mkdir run-proof && cd run-proof
python ../run_mcts.py init --state-file ../proof.md --iterations 50 \
  --batch-size 3 --wildness 0.15 \
  --moves '[
    {"desc":"State the sieve bound as a numbered lemma with explicit constants","prior":0.4,"risk":"safe"},
    {"desc":"Replace the informal for-large-enough-x with an explicit epsilon-N definition","prior":0.35,"risk":"safe"},
    {"desc":"Reorganize: prove the parity barrier lemma before the main argument","prior":0.25,"risk":"bold"}]'

# Loop (50 times): step -> realize -> record. Score against:
# logical validity (dominant weight), completeness of cases, clarity of exposition.
# A move that silently strengthens an unstated hypothesis must be scored LOW
# even if the resulting text reads cleaner.
python ../run_mcts.py step
# ... edit the proof, write ../proof-v2.md ...
python ../run_mcts.py record --node-id n_0 --action-id act_3 \
  --new-state-path ../proof-v2.md --value 0.48 \
  --moves '[{"desc":"Add the missing Case 2 for p ≡ 1 (mod 4)","prior":0.5,"risk":"safe"},
            {"desc":"Factor the counting argument into its own subsection","prior":0.3,"risk":"safe"},
            {"desc":"Switch the whole approach to Selberg sieve weights","prior":0.2,"risk":"bold"}]'

python ../run_mcts.py best
```

The rubric dominance matters here: score `value = 0.7*(rigor) + 0.2*(case
completeness) + 0.1*(clarity)` and be harsh — an unproven "standard" step
caps the whole state's value around 0.5 regardless of polish.

### Example 4: Refining a directory (HTML/CSS/assets) toward an AAA web design

Goal: turn a plain multi-page site into a polished AAA-game-quality design.
The artifact is a directory, so every state is a full directory copy — the
agent edits a copy of the tree, then points `record` at it. Structure changes
(new files, renamed assets) are normal moves here.

```bash
mkdir run-website && cd run-website
python ../run_mcts.py init --state-file ../site/ --iterations 60 \
  --batch-size 4 --wildness 0.3 \
  --moves '[
    {"desc":"Establish a design-token system: add tokens.css with type/color/spacing scale","prior":0.35,"risk":"safe"},
    {"desc":"Rebuild index.html hero with layered gradients, glass cards, animated CTA","prior":0.3,"risk":"bold"},
    {"desc":"Introduce scroll-driven parallax + staggered section reveals in main.js","prior":0.25,"risk":"wild"},
    {"desc":"Swap the whole palette to a dark neon theme with gradient accents","prior":0.1,"risk":"wild"}]'

# Loop (60 times): step -> read the whole state tree -> edit a copy -> record
python ../run_mcts.py step
# status=ready_for_eval -> read .mcts_artifacts/n_0.state/ (index.html, css/, js/, assets/)
# ... make edits on a copy: cp -r .mcts_artifacts/n_0.state ../site-draft && edit ../site-draft ...
python ../run_mcts.py record --node-id n_0 --action-id act_2 \
  --new-state-path ../site-draft --value 0.55 \
  --moves '[{"desc":"Add hover micro-interactions and focus states to all CTAs","prior":0.35,"risk":"safe"},
            {"desc":"Design a consistent nav + footer system across all pages","prior":0.3,"risk":"bold"},
            {"desc":"Add a WebGL/canvas background layer with particle field","prior":0.2,"risk":"wild"},
            {"desc":"Convert all raster icons to inline SVG sprite system","prior":0.15,"risk":"bold"}]'

python ../run_mcts.py best   # last state_ref = the whole refined site directory
```

Directory tips: keep `--iterations` moderate (directories multiply the
content you regenerate per move); score the state as a *coherent whole*
(visual hierarchy, consistency across pages, performance sanity), and treat
"added a file" as part of the move description — e.g. "Add `tokens.css`
defining the spacing scale" — since the trajectory should read as a changelog.
