---
name: mcts-refine
description: Use when the user wants to iteratively refine text, code, prompts, or other artifacts using Monte Carlo Tree Search (PUCT + progressive widening). Triggers on requests like "refine this with MCTS", "tree-search this draft against a rubric", or "explore edits and pick the best". Drives init/step/propose/record/best cycles via run_mcts.py to search a branching tree of edits toward an objective.
---

# MCTS Refinement

Refine an artifact by searching a tree of edits. The bundled Python harness
(`run_mcts.py`) is intentionally **dumb**: it only does bookkeeping (PUCT
selection, backpropagation, copying artifact paths around) and never opens,
reads, or renders artifact content itself — it only ever touches its own
working files (`.mcts_tree.json`, `.mcts_artifacts/`). **You, the agent,
supply all the semantics and do all the reading/writing of the actual
artifact** — you are both the *policy* (proposing a full batch of moves +
priors per node, AlphaZero-style) and the *critic* (scoring the resulting
states), using your own Read/Glob/Edit/bash tools to inspect and produce
artifact content. The harness just hands you a path.

The harness has NO internal loop and calls no model. You drive it.

## Guardrails: use the harness as-is, don't go around it

- **Never write your own script to reimplement, simulate, or replace this
  search.** Don't author a Python/JS/shell/etc. program that does your own
  tree search, PUCT math, priors, or batch orchestration instead of calling
  `python run_mcts.py init/step/propose/record/best`. The engine and CLI are
  already implemented and tested — reinventing them mid-task is exactly what
  this skill exists to prevent. Every search-related action is one of the
  five documented subcommands, invoked via `bash`, nothing else.
- **This restriction is about the search mechanics, not the artifact.** If
  the artifact *being refined* is itself code or a script, writing/editing
  that code is the whole point — do it freely with your normal tools. The
  line is: harness logic (tree, selection, bookkeeping) = never
  reimplemented; artifact content (which may be code) = yours to write.
- If you notice yourself about to write a `.py`/`.js`/`.sh` file whose
  purpose is to drive iterations, score states, or manage the tree, stop —
  that's the harness's job. Call `run_mcts.py` instead.
- **Named anti-pattern: do not parallelize `step`/`record` against a shared
  tree.** Firing concurrent `step`/`record` calls (threads, background
  processes, batched subprocess calls) at the *same* `.mcts_tree.json` is not
  a clever speedup — there is no locking, so racing reads/writes can corrupt
  the tree (lost updates, duplicate node IDs from a stale `_node_counter`,
  broken parent/child links) silently, with no error to warn you. It also
  breaks PUCT itself: `select()` depends on the *previous* call's
  backpropagated visit counts being visible before the next selection runs —
  concurrent calls select against stale statistics, defeating the exploration
  term. MCTS over one tree is inherently sequential; there is no legitimate
  way to run it "in parallel" against a single `.mcts_tree.json`. If you
  genuinely need concurrency, the only sound form is *root parallelization*:
  separate `init` runs in separate working directories (different CWDs, each
  with its own tree), compared/merged only at the end by looking at each run's
  `best` output side by side — never by touching another run's tree file.
- **The search's wall-clock speed is not your concern and is not a signal
  to act on.** Each iteration is one LLM round-trip by design — that is the
  cost of a real policy+critic step, not inefficiency to fix. Slowness is
  never a valid reason to parallelize, batch-fake iterations, shortcut
  scoring, reduce the budget without being asked, or otherwise deviate from
  the documented loop. If the budget feels large, that's a decision for the
  user to make via `--iterations`, not something to route around mid-run.

## Cleanup discipline (leave the directory tidy)

- All search scaffolding is disposable: `.mcts_tree.json`, `.mcts_artifacts/`,
  and any scratch files/directories you created along the way to hold an
  edited state before `record` (e.g. `edited-draft.txt`, temp directory
  copies) — anything that isn't the original artifact, `refine.md`, or the
  final `one`/`two`/`three` deliverables.
- **Delete all of it once `best` has run and `one`/`two`/`three` are safely
  copied out.** After verifying the delivered copies exist on disk and are
  complete, remove `.mcts_tree.json`, `.mcts_artifacts/`, and every scratch
  intermediate-state file/dir you made during the loop (`rm -rf`/`rm` with
  your bash tool). Do this as the last step of every search, no exceptions —
  don't leave a `.mcts_tree.json` or `.mcts_artifacts/` sitting in the
  working directory once the run is delivered.
- Keep only: the original artifact (untouched), `refine.md` (the log,
  finished with its summary), and `one`/`two`/`three`. Nothing else should
  remain in the search's working directory afterward.
- If the search is interrupted or abandoned before `best` (rare — see "Do
  not stop early" below), leave the tree/artifacts in place so it can be
  resumed with `step`; only clean up once a run actually finishes.

## Reporting discipline (user-facing output)

While the search runs, the stats go to a log file — **`refine.md` in the
search's working directory** — not into the chat.

- **Per iteration, append exactly one stats line to `refine.md`**, lc0-
  `info` style, built from the harness response's iteration progress +
  `total_nodes` + `tree_max_depth` + `root_children` top-3 (moves ranked by
  visits, with prior/Q):
  `iter 37/100 · nodes 52 · maxdepth 6 · N(act_2)=18 Q=0.71 P=0.40 | N(act_1)=12 Q=0.65 P=0.30 | N(act_4)=5 Q=0.58 P=0.15 | ...`
  One line per iteration, appended in order; `refine.md` is the run's
  progress log. Create it at `init`, and at the end append the final summary
  (ranked root moves with `visits`/`q_value`/`subtree_nodes`/`subtree_depth`
  and the three delivered paths).
- **Nothing goes to the chat during the loop.** Do not emit the stats line,
  the shell commands you run (`python run_mcts.py step ...`), their JSON
  output, the move batches you propose, priors or values you assign, files
  you read or wrote, tool results, or any other intermediate evidence. All
  of that is machine-to-machine; the harness JSON is for you to parse and
  act on, `refine.md` is where the stats live. The user follows progress by
  opening `refine.md`.
- **Do not report on the work product** — the artifact's actual content
  (draft text, code, diff excerpts, scores narrated as progress) — until the
  search is over. While the budget is running, `refine.md` carries only the
  stats lines; quoting, summarizing, or narrating artifact content mid-run
  defeats the point of running the search.
- **At the end** (`best`), append the final summary to `refine.md`: the
  ranked root moves with `visits`/`q_value`/`subtree_nodes`/`subtree_depth`
  (node count and depth per root move) and the winning concept. **Deliver
  the top three concepts as `one`/`two`/`three`**, named appropriately to
  the artifact: copy each ranked concept's `leaf_state_ref` next to the
  original (same extension for files — `one.md`, `two.md`, `three.md` for a
  markdown input; a whole directory copied as `one/`, `two/`, `three/` for
  a directory artifact). `one` is the search's winner. **The original
  artifact is never modified** — all refinement lives in the copies. Still
  no raw JSON, and never paste artifact content into the chat; if the user
  wants to read a result, they open the file or `refine.md`.

## The four MCTS concepts, mapped to refinement

| MCTS term | In this skill | Where it goes |
| --------- | ------------- | ------------- |
| **State** | The full artifact at a node — the current version of the text/code/prompt/project, referenced by *path*, not embedded as text. Self-contained, not a diff. | `--state-file <path>` at `init` (required — see below); `--new-state-path <path>` at `record`. The harness copies it into `.mcts_artifacts/n_X.state` and returns that `state_ref`; you read it yourself. |
| **Move** (action) | A single proposed transformation of a state → a new child state. Described in plain language; you register it (with siblings) before it's expanded, then apply it to produce the new state when PUCT selects it. | `{"desc": "...", "prior": ..., "risk": "safe"\|"bold"\|"wild"}` entries via `--moves`/`--moves-file` at `init`/`propose`/`record`. |
| **Prior** | Your *pre-evaluation* estimate of how promising a move is, as one entry in a probability distribution over **all** sibling moves from that node (they must sum to ~1.0 — see below). Biases PUCT toward promising-but-unexpanded branches. | the `"prior"` field in each `--moves` entry |
| **Evaluation** (value) | Your *post-hoc* critic score, in `[0,1]`, of how well the resulting child state satisfies the objective rubric. Backpropagated to update Q-values up the tree. | `--value <v>` at `record` |

### Invocation requirement: the artifact must be a file or directory path
- `init --state-file <path>` is **required** and must point to a real file or
  directory on disk — inline text is not accepted for the artifact you're
  asked to refine. If invoked without a path (e.g. the user only pastes text
  inline), first write that text to a scratch file yourself with your own
  tools, then pass that path to `--state-file`.
- **File artifact**: a single document/script. `artifact_kind` in every
  response is `"file"`.
- **Directory artifact**: a whole project/multi-file artifact — `init` copies
  the entire directory tree as the root state. `artifact_kind` is
  `"directory"`. Every subsequent state for that tree must also be recorded
  as a directory via `record --new-state-path <path>` (materialize your
  edited copy of the whole tree on disk with your own tools, then point at
  it).
- **The harness never reads artifact content.** `step`/`best` give you
  `state_ref` — a path under `.mcts_artifacts/` — and `artifact_kind`
  (`"file"`/`"directory"`), nothing more. Use your own Read/Glob/bash tools on
  that path to see what's actually in the state before proposing/realizing a
  move. There is no `state_content` field to rely on.

### How to describe a STATE
- Produce the **complete artifact**, not a patch — write it to disk (a file or
  directory) with your own tools, then hand `record` that path via
  `--new-state-path`. Each node must stand alone so `best` can extract it
  directly. For code, that's the whole file/function (or whole directory
  tree, for directory artifacts); for prose, the whole document.
- Keep it in the same medium as the input (markdown in, markdown out).

### How to propose MOVES (the policy step)
- Whenever you create a node (`init` for the root, or `record` for a new
  child), propose its **full set of candidate next moves in one batch** —
  don't dribble them out one at a time. This mirrors a policy head emitting a
  distribution over all legal moves in one forward pass.
- Each move is `{"desc": "...", "prior": <0..1>, "risk": "safe"|"bold"|"wild"}`.
  One coherent change per move: *"Tighten the intro to two sentences and add a
  concrete benchmark table"*, not *"improve everything"*.
- Generate **distinct** sibling moves — genuinely different directions
  (restructure vs. add evidence vs. cut length), not near-duplicates. This
  applies within a batch (siblings), but also **check the lineage**: before
  proposing a new batch for a node, glance at the `action` labels already
  applied on the path from ROOT to that node (visible in `step`'s
  `existing_actions`/trajectory context, or `best`'s `trajectory` once
  available) and don't re-propose a move that's essentially the same thing
  already done one or two levels up. "Add concrete benchmarks" chosen at
  depth 2 and then proposed again, near-verbatim, as a depth-3 child move is
  wasted budget, not refinement — the artifact already has that change; the
  next batch should build on it or try something new, not repeat it. A
  string of near-identical moves winning selection in a row is a signal your
  batches aren't actually distinct from what's already in the state, not
  that the search "wants" that move — diversify the next batch instead of
  reproposing it.
- The `desc` is what shows up in the `best` trajectory, so make it a readable
  changelog entry. The actual change is only produced later, lazily, when
  PUCT actually selects that move for expansion (see Workflow).

#### Batch size and wildness (how many moves, how far to push them)
- `init --batch-size <n>` (default `4`) sets your **target** number of moves
  per batch — a reminder, echoed in every `step`/`propose`/`record` response
  as `target_batch_size`. The harness doesn't enforce it (it can't generate
  moves), but treat it as the number to aim for each time you propose.
- `init --wildness <0..1>` (default `0.25`) sets the **target fraction of each
  batch that should be genuinely risky/experimental** moves, tagged
  `"risk": "wild"`. Also echoed back as `target_wildness`.
- Tag every move with a `risk` level:
  - `"safe"` — incremental, high-confidence, low blast radius (typo fixes,
    small clarifications).
  - `"bold"` — a real, structural change you have decent conviction in
    (default if omitted).
  - `"wild"` — a genuine long-shot: break the format, invert an assumption,
    try a structure or voice you wouldn't normally risk. Low conviction is
    fine — the whole point is to occasionally explore outside the safe
    neighborhood the search would otherwise converge on. Give these a lower
    but non-trivial prior (e.g. `0.1–0.2`) so PUCT samples them sometimes
    without letting them dominate visits.
  - Higher `--wildness` → include more/bigger wild swings per batch (and/or
    make the "wild" entries more extreme); lower `--wildness` → stay close to
    incremental refinement. Adjust it live per node if a task calls for it —
    e.g. widen it after several batches plateau at similar scores, narrow it
    once you've found a strong direction and want to polish it.
  - If a batch of 3+ moves has zero `"wild"` entries while `wildness > 0`,
    the harness returns a nudge `warning` — don't ignore it; add a riskier
    option (or lower `--wildness` at the next `init` if the task genuinely
    doesn't call for exploration, e.g. a narrow bugfix).

### How to assign PRIORS
- Answer, for each move: *before I even see the result, how likely is this
  move to help, relative to its siblings?*
- **Priors in a single batch must sum to 1.0** (like a softmax policy output)
  — they are a distribution over "what could I do from here," not independent
  scores. Use the full range within that budget: e.g. `0.5 / 0.3 / 0.2` for a
  high-conviction favorite plus two plausible alternatives, or spread more
  evenly (`0.34/0.33/0.33`) when genuinely unsure.
- The harness **normalizes-and-warns** rather than rejecting: if a batch's
  priors don't sum to 1.0 (within 1e-3), it rescales them proportionally
  (or resets to uniform if the sum is `<= 0`) and returns a `warning` string.
  Don't ignore that warning — it means your stated priors didn't reflect a
  real distribution; do the arithmetic more carefully next batch.
- The single-move ad hoc fallback (`record` with `--desc`/`--prior`, no
  `--action-id`) is exempt from this — there's only one entry, so its prior is
  used as-is. Prefer batched `--moves` whenever you can see more than one
  reasonable next step.

### Avoiding shell-quoting breakage
Move descriptions and artifact text routinely contain quotes, apostrophes, or
backticks (quoting a line of prose, a code snippet, etc.), which breaks
inline shell arguments. **Always use the file-based forms, never inline
JSON/text on the command line:**
- `--moves` (init/propose/record) → write the JSON array with your Write tool
  to a scratch file (e.g. `.mcts_scratch/moves.json`) and pass
  `--moves-file <path>` instead. This is a scratch file — clean it up with
  the rest of the search scaffolding.
- `--desc` (record's ad hoc single-move fallback) → write the description
  text to a scratch file and pass `--desc-file <path>` instead.
- The artifact itself (`--state-file`/`--new-state-path`) is already
  path-based, so it's unaffected — only move/description *text* is at risk.
- Treat inline `--moves`/`--desc` as a shortcut for trivial, quote-free
  strings only; default to the `-file` variants whenever in doubt.

### How to assign a VALUE (evaluation)
- Score the **resulting state against the objective**, independent of the prior.
  A move with a modest prior can still yield a high-value state (pleasant
  surprise) — that's exactly what the search should discover.
- Be a consistent, calibrated critic across the whole run: anchor `1.0` =
  fully meets the rubric, `0.0` = fails it, and grade the artifact on its
  merits each time. Inconsistent scoring corrupts the Q-values that guide
  selection.
- If the objective has sub-criteria, score them mentally and average — but emit
  a single scalar.

## Workflow

Default budget: **100 iterations** (each iteration = one realized/expanded
move, i.e. one new node with a state + value — proposing a batch of moves on
a node does not by itself consume an iteration).

**Do not stop early.** The harness has no internal loop and does not enforce
the budget — that is entirely on you. Keep looping until `iterations_done` in
the `step`/`record` JSON reaches `target_iterations` (equivalently
`iterations_remaining` hits `0` / `target_reached` is `true`). Running out of
"obvious" moves, hitting a good-looking score, or context pressure are not
valid reasons to stop short — invent another distinct move and keep going.
Only a hard error (e.g. corrupted tree state) justifies halting before the
budget is spent, and even then, say so explicitly rather than quietly
finishing early.

1. **Init** the tree with the starting artifact, the full iteration budget,
   and the root's first batch of candidate moves (priors summing to ~1.0).
   `--state-file <path>` is **required** and must be a real file or directory
   on disk (see "Invocation requirement" above). **Call `init` exactly once per
   search, at the very start.** If a tree already exists in the CWD, `init`
   *refuses to run* (error) — it will not silently wipe a prior search's tree
   or spawn a second root; that error is your signal to continue the existing
   search (via `step`) rather than restart. Only pass `--force-restart` when
   you are deliberately and explicitly discarding all prior refinement work.
   ```bash
   python run_mcts.py init --state-file <path/to/file-or-directory> --iterations 100 \
     --batch-size 4 --wildness 0.25 \
     --moves '[{"desc":"...","prior":0.5,"risk":"safe"},{"desc":"...","prior":0.3,"risk":"bold"},{"desc":"...","prior":0.2,"risk":"wild"}]'
   ```
   The response's `artifact_kind` confirms whether it registered as `"file"`
   or `"directory"` — check it matches what you intended. `state_ref` is the
   path the harness copied your artifact to; read it yourself if you need to
   confirm its contents (the response never embeds the content).
   (Omit `--iterations`/`--batch-size`/`--wildness` to keep their defaults of
   `100`/`4`/`0.25`. `--moves` is optional at init — if skipped, the first
   `step` will report `ready_for_moves` and you propose them then via
   `propose`.) Watch for `proposed_moves_warning` in the response — if
   present, your priors were normalized because they didn't sum to 1.0, or you
   were nudged to add a `"wild"` move.

2. **Loop** until the budget is exhausted:
   - Select a node/move to work on:
     ```bash
     python run_mcts.py step
     ```
     Read the JSON `status`:
     - `ready_for_moves`: `target_node_id` has no candidate moves registered
       yet. Propose a batch for it (policy step, no state/value needed yet):
       ```bash
       python run_mcts.py propose --node-id <target_node_id> \
         --moves '[{"desc":"...","prior":0.6,"risk":"safe"},{"desc":"...","prior":0.4,"risk":"wild"}]'
       ```
       Aim for `target_batch_size` moves with roughly `target_wildness`
       fraction tagged `"wild"` (both echoed in the `step` response).
       Then call `step` again — PUCT will now pick among them.
     - `ready_for_eval`: PUCT selected a specific unexpanded move,
       `target_action_id`, with its already-registered `action_description`,
       `action_prior`, and `action_risk` on `target_node_id`. Read the current
       state yourself at `state_ref` (using your own tools — a file or, for
       directory artifacts, browse the tree), apply that move to produce the
       new state on disk, score it, and `record` it (see below) — do **not**
       invent a different move than the one named. If `action_risk` is
       `"wild"`, actually push the artifact somewhere genuinely different —
       don't quietly downgrade a wild move into a safe edit just because it
       feels safer to execute.
     - `no_actionable_node`: terminal/depth-capped dead end; treat as
       exhausted and `step` again (selection will land elsewhere) — should be
       rare with `max_depth` unlimited.
      After each `step`/`propose`/`record` in the loop, append the single
      per-iteration stats line to `refine.md` (per Reporting discipline):
      `iterations_done`/`target_iterations`, `total_nodes`,
      `tree_max_depth`, and the `root_children` top-3 readout. Nothing
      else, to the log or the chat — no commands, no JSON, no content, no
      evidence.
   - **As critic**: score the new state against the objective → `value`.
   - Write the edited artifact to disk yourself (a scratch file, or a full
     copy of the directory tree with your edit applied — your choice of
     location), then record the realized move by pointing at that path
     (optionally seeding the *new* child's own next batch of candidate moves
     in the same call):
     ```bash
     python run_mcts.py record \
       --node-id <target_node_id> \
       --action-id <target_action_id> \
       --new-state-path <path/to/your/edited/file-or-directory> \
       --value <0..1> \
       --moves '[{"desc":"...","prior":0.5,"risk":"bold"}, {"desc":"...","prior":0.5,"risk":"wild"}]'
     ```
     `--new-state-path` is required and must be a real path (file or
     directory, matching the root artifact's kind) — the harness has no
     inline-text option; it just copies whatever you point it at. Only fall
     back to ad hoc `--desc`/`--prior` (no `--action-id`) if you truly need to
     add a single move outside any batch — its prior is used as-is,
     unnormalized.
      The response repeats `iterations_done`, `iterations_remaining`,
      `target_reached`, `total_nodes`, `tree_max_depth`, and the
      `root_children` top-3 — that's the source for the next stats line in
      `refine.md`. Stay silent otherwise.
   - If `target_reached` is `false`, go back to `step` and continue. Do not
     move on to `best` until it is `true`.

3. **Extract** the winning trajectory (walks by max visit count) only after
   the full budget has been used:
   ```bash
   python run_mcts.py best
   ```
   `best` returns `top_concepts` (default 3, or pass `--top <n>`): the root's
   strongest strategic directions, each as its own robust-child trajectory
   ranked by leaf visit count (tie-break on Q). For each: `rank`, `concept`
   (the first move's description), `final_q_value`/`final_visits`/`depth`,
   `subtree_nodes`/`subtree_depth` (size and depth of that root direction's
   subtree — report these per root move in the final summary),
   `leaf_state_ref` (that concept's refined artifact on disk), and the full
   `trajectory` chain. The output also includes a complete `root_children`
   list (all root moves, ranked by visits, with subtree stats).

   **Deliver the results**: copy the top three concepts' `leaf_state_ref` to
   `one`/`two`/`three`, named appropriately to the artifact kind —
   `one.md`/`two.md`/`three.md` for a markdown file input (same extension as
   the original), `one/`/`two/`/`three/` for a directory artifact — with
   `one` = rank 1 (the winner). Append the final summary to `refine.md`
   (ranked root moves with node counts and depths, plus the three delivered
   paths); never paste artifact content into the chat, and leave the
   original artifact unmodified. The output also echoes final
   `iterations_done`/`target_iterations`, `total_nodes`, and
   `tree_max_depth` as a confirmation the full search ran.

4. **Clean up.** Once `one`/`two`/`three` are copied out and confirmed on
   disk, delete `.mcts_tree.json`, `.mcts_artifacts/`, and any scratch
   intermediate-state files/dirs you created during the loop for `record`
   calls — see "Cleanup discipline" above. This is a required last step of
   every run, not optional tidying.

## Tuning knobs (in `engine.py`, optional)
- `c_puct` (1.414): higher = more exploration of high-prior branches.
- `max_depth` (0 = unlimited): longest single refinement chain. Unlimited by
  default, so the search may build arbitrarily deep trajectories; set a positive
  value only if you want to cap chain length.
- `widening_c` / `widening_alpha` (1.5 / 0.5): legacy knobs from an earlier
  one-move-at-a-time design. Since moves are now proposed in full batches up
  front (like a policy head), PUCT already governs branch selection over the
  whole known action set and these are currently unused by `select()`. Kept
  for backward-compatible tree-file loading only.

## State on disk
- `.mcts_tree.json` — tree metadata (stats, topology, priors), rewritten each call.
- `.mcts_artifacts/n_X.state` — one file or directory per node, a plain copy
  of whatever you passed via `--state-file`/`--new-state-path`. The harness
  only ever `shutil.copy`/`copytree`s these — it never opens them to read or
  render content.

Both live in the CWD under fixed names, so run each search in its own working
directory to avoid collisions. There is exactly one tree and one root per
directory; `init` refuses to overwrite an existing tree (unless you explicitly
pass `--force-restart`), and `step`/`propose`/`record` error out if no tree
exists yet.

**Both are scratch, not deliverables** — they exist only to let the search
resume via `step` while it's in progress. Once `best` has run and
`one`/`two`/`three` are delivered, delete them (see "Cleanup discipline").
A finished search directory should contain only the original artifact,
`refine.md`, and `one`/`two`/`three` — not `.mcts_tree.json` or
`.mcts_artifacts/`.
