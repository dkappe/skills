---
name: mcts-refine
description: Use when the user wants to iteratively refine text, code, prompts, or other artifacts using Monte Carlo Tree Search (PUCT + progressive widening). Triggers on requests like "refine this with MCTS", "tree-search this draft against a rubric", or "explore edits and pick the best". Drives init/step/record/best cycles via run_mcts.py to search a branching tree of edits toward an objective.
---

# MCTS Refinement

Refine an artifact by searching a tree of edits. The bundled Python harness
(`run_mcts.py`) does the bookkeeping (PUCT selection, progressive widening,
backpropagation); **you, the agent, supply all the semantics** — you are both
the *policy* (proposing moves + priors) and the *critic* (scoring states).

The harness has NO internal loop and calls no model. You drive it.

## The four MCTS concepts, mapped to refinement

| MCTS term | In this skill | Where it goes |
| --------- | ------------- | ------------- |
| **State** | The full artifact content at a node — the current version of the text/code/prompt. Self-contained, not a diff. | `--state-file` / `--state` at `init`; `--new-state-file` / `--new-state` at `record`. Stored in `.mcts_artifacts/n_X.state`. |
| **Move** (action) | A single proposed transformation of the parent state → a new child state. Described in plain language, applied by you to produce the new state. | `--desc "..."` (the human-readable move) plus the resulting `--new-state`. |
| **Prior** | Your *pre-evaluation* estimate, in `[0,1]`, of how promising this move is relative to sibling moves. A policy probability. Biases PUCT toward promising-but-untried branches. | `--prior <p>` |
| **Evaluation** (value) | Your *post-hoc* critic score, in `[0,1]`, of how well the resulting child state satisfies the objective rubric. Backpropagated to update Q-values up the tree. | `--value <v>` |

### How to describe a STATE
- Emit the **complete artifact**, not a patch. Each node must stand alone so
  `best` can extract it directly. For code, that's the whole file/function; for
  prose, the whole document.
- Keep it in the same medium as the input (markdown in, markdown out).

### How to describe a MOVE
- One coherent change per move: *"Tighten the intro to two sentences and add a
  concrete benchmark table"*, not *"improve everything"*.
- The `--desc` is what shows up in the `best` trajectory, so make it a readable
  changelog entry. The actual change lives in `--new-state`.
- Generate **distinct** sibling moves. Progressive widening only lets a node
  sprout a few children early on, so make each one a genuinely different
  direction (restructure vs. add evidence vs. cut length), not near-duplicates.

### How to assign a PRIOR
- Answer: *before I even see the result, how likely is this move to help,
  compared to the other moves I could make from this node?*
- Use the full range. `0.8–0.9` = high-conviction structural fix; `0.4–0.6` =
  plausible; `0.1–0.2` = speculative long shot you still want represented.
- Priors need not sum to 1 across siblings, but treat them *relatively* — PUCT
  multiplies prior by exploration bonus, so a higher prior means "visit me
  sooner".

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

Default budget: **100 iterations** (each iteration = one `step` + one `record`,
adding exactly one node). Enforce this count yourself; the harness will not.

1. **Init** the tree with the starting artifact:
   ```bash
   python run_mcts.py init --state-file <artifact>
   ```

2. **Loop** (default 100 times):
   - Select a node to work on:
     ```bash
     python run_mcts.py step
     ```
     Read the JSON: `target_node_id`, `state_content` (the state to improve),
     `existing_actions` (moves already tried here — avoid duplicating them),
     `needs_expansion`, `depth`, `q_value`, `visits`.
   - **As policy**: invent one new distinct move for that state, decide its
     `prior`, and produce the full edited `new-state`.
   - **As critic**: score the new state against the objective → `value`.
   - Record it:
     ```bash
     python run_mcts.py record \
       --node-id <target_node_id> \
       --desc "<the move, as a changelog line>" \
       --prior <0..1> \
       --new-state "<the complete edited artifact>" \
       --value <0..1>
     ```
     For large artifacts, write to a temp file and use `--new-state-file`
     instead of `--new-state`.

3. **Extract** the winning trajectory (walks by max visit count):
   ```bash
   python run_mcts.py best
   ```
   The last node's `state_content` is the refined artifact; the `action` chain
   is the story of how it got there.

## Tuning knobs (in `engine.py`, optional)
- `c_puct` (1.414): higher = more exploration of high-prior branches.
- `widening_c` / `widening_alpha` (1.5 / 0.5): how many children a node earns
  per visit — raise for broader search, lower for deeper.
- `max_depth` (0 = unlimited): longest single refinement chain. Unlimited by
  default, so the search may build arbitrarily deep trajectories; set a positive
  value only if you want to cap chain length.

## State on disk
- `.mcts_tree.json` — tree metadata (stats, topology, priors), rewritten each call.
- `.mcts_artifacts/n_X.state` — one file per node holding that node's full state.

Both live in the CWD under fixed names, so run each search in its own working
directory to avoid collisions, and clean up stale `.state` files between runs.
