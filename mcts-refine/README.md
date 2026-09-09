# MCTS Refinement Skill for OpenCode

Monte Carlo Tree Search (MCTS) engine featuring **PUCT** (Polynomial Upper Confidence Trees) and **Progressive Widening** for stateful artifact refinement (text, code, prompts, image generation latents/diffs).

## Architecture

- **`skill.json`**: OpenCode skill definition with metadata and tool schema.
- **`engine.py`**: Clean, JSON-serializable PUCT engine with progressive widening and node-level statistics.
- **`run_mcts.py`**: CLI harness designed for LLM agents to execute `init`, `step`, `record`, and `best` operations.
- **JSON state & Artifact Cache**: Metadata is stored in `.mcts_tree.json` and artifact states are decoupled into `.mcts_artifacts/` to keep tree operations fast and light.

## Usage Walkthrough

1. **Initialize the search tree**:
   ```bash
   python run_mcts.py init --state-file draft.txt
   ```

2. **Select node to expand**:
   ```bash
   python run_mcts.py step
   ```

3. **Record child node, action prior, and critic evaluation**:
   ```bash
   python run_mcts.py record \
     --node-id "n_0" \
     --desc "Add concrete benchmarks and simplify introduction" \
     --prior 0.75 \
     --new-state "Updated artifact content..." \
     --value 0.85
   ```

4. **Extract the highest-visit optimal trajectory**:
   ```bash
   python run_mcts.py best
   ```
