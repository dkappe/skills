import argparse
import json
import shutil
from pathlib import Path
from engine import JsonMCTSEngine, MCTSNode, Action

TREE_FILE = Path(".mcts_tree.json")
ARTIFACTS_DIR = Path(".mcts_artifacts")


def get_engine() -> JsonMCTSEngine:
    if TREE_FILE.exists():
        return JsonMCTSEngine.load(TREE_FILE)
    raise ValueError(
        "No search tree found in this directory (.mcts_tree.json does not exist). "
        "Run 'init --state-file <path>' first — never create nodes outside the tree."
    )


def load_moves(args):
    moves_file = getattr(args, "moves_file", None)
    moves_raw = getattr(args, "moves", None)
    if moves_file:
        return json.loads(Path(moves_file).read_text())
    if moves_raw:
        return json.loads(moves_raw)
    return None


def copy_state(src: Path, dest: Path) -> str:
    """Copy a file or directory artifact path into the artifact cache, purely
    as an opaque blob — the harness never opens/reads/renders the contents.
    Returns "file" or "directory" (just an is_dir() check) so callers can
    report artifact_kind."""
    if not src.exists():
        raise ValueError(f"Artifact path does not exist: {src}")
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        return "directory"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
    return "file"


def stats_block(engine: JsonMCTSEngine) -> dict:
    """Shared progress block: iteration progress, node count, tree depth, and
    the LC0-style root readout (the root's candidate moves ranked by visits).
    Pure tree bookkeeping from .mcts_tree.json — the harness never reads
    artifact content."""
    return {
        "iterations_done": engine.iterations_done(),
        "target_iterations": engine.target_iterations,
        "iterations_remaining": max(0, engine.target_iterations - engine.iterations_done()),
        "total_nodes": len(engine.nodes),
        "tree_max_depth": engine.tree_max_depth(),
        "root_children": engine.root_children_stats(top_n=3),
    }


def cmd_init(args):
    if not args.state_file:
        raise ValueError(
            "The artifact to refine must be specified as a file or directory path via "
            "--state-file. Inline/ad hoc text content is not accepted at init."
        )

    if TREE_FILE.exists():
        if not args.force_restart:
            raise ValueError(
                "A search tree already exists in this directory (.mcts_tree.json present, "
                f"root {json.loads(TREE_FILE.read_text()).get('root_id')} of "
                f"{len(json.loads(TREE_FILE.read_text())['nodes'])} node(s)). Do NOT re-init to "
                "start a second search or create another root — that discards the existing tree "
                "and its refinement history. Continue the current search instead: call 'step' to "
                "select a node/move and work from there. Only pass --force-restart if you are "
                "intentionally and explicitly discarding ALL prior refinement work to start over "
                "from scratch."
            )
        TREE_FILE.unlink()
        if ARTIFACTS_DIR.exists():
            shutil.rmtree(ARTIFACTS_DIR)
    elif ARTIFACTS_DIR.exists() and any(ARTIFACTS_DIR.iterdir()):
        if not args.force_restart:
            existing = sorted(p.name for p in ARTIFACTS_DIR.iterdir())
            raise ValueError(
                "No .mcts_tree.json found in this directory, but .mcts_artifacts/ already contains "
                f"{len(existing)} artifact file(s)/dir(s) (e.g. {existing[0]}..{existing[-1]}). This "
                "looks like the tree file from a prior search went missing (wrong working directory, "
                "manual deletion, etc.) while its artifacts survived — running init here would silently "
                "start a brand-new root without ever touching those old artifacts, orphaning them and "
                "losing all prior visit/Q-value history with no error. Do NOT re-init to 'fix' this. "
                "Investigate first (check you're in the right working directory; look for the tree file "
                "elsewhere). Only pass --force-restart if you are intentionally and explicitly discarding "
                "ALL prior refinement work — this will also delete the existing .mcts_artifacts/ directory."
            )
        shutil.rmtree(ARTIFACTS_DIR)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    engine = JsonMCTSEngine(
        target_iterations=args.iterations,
        batch_size=args.batch_size,
        wildness=args.wildness,
    )

    root_state_ref = ARTIFACTS_DIR / "n_0.state"
    artifact_kind = copy_state(Path(args.state_file), root_state_ref)

    root_node = MCTSNode(node_id="n_0", state_ref=str(root_state_ref))
    engine.root_id = "n_0"
    engine.nodes["n_0"] = root_node

    moves = load_moves(args)
    proposed_action_ids, warning = engine.add_actions(root_node, moves) if moves else ([], None)

    engine.save(TREE_FILE)

    print(json.dumps({
        "status": "initialized",
        "root_id": "n_0",
        "state_ref": str(root_state_ref),
        "artifact_kind": artifact_kind,
        "target_iterations": engine.target_iterations,
        "iterations_done": 0,
        "iterations_remaining": engine.target_iterations,
        "target_batch_size": engine.batch_size,
        "target_wildness": engine.wildness,
        "proposed_action_ids": proposed_action_ids,
        "proposed_moves_warning": warning,
        "forced_restart": bool(args.force_restart),
        **stats_block(engine)
    }))


def cmd_propose(args):
    engine = get_engine()
    if args.node_id not in engine.nodes:
        raise ValueError(f"Target node {args.node_id} not found in search tree.")
    node = engine.nodes[args.node_id]

    moves = load_moves(args)
    if not moves:
        raise ValueError("Must supply --moves or --moves-file with at least one {\"desc\", \"prior\"} entry.")

    action_ids, warning = engine.add_actions(node, moves)
    engine.save(TREE_FILE)

    print(json.dumps({
        "status": "proposed",
        "node_id": node.node_id,
        "action_ids": action_ids,
        "actions": [
            {
                "action_id": aid,
                "description": node.actions[aid].description,
                "prior": node.actions[aid].prior,
                "risk": node.actions[aid].risk,
            }
            for aid in action_ids
        ],
        "warning": warning,
        "target_batch_size": engine.batch_size,
        "target_wildness": engine.wildness,
        **stats_block(engine)
    }))


def cmd_step(args):
    engine = get_engine()
    path, pending_action_id, needs_moves = engine.select()
    leaf = path[-1]
    engine.save(TREE_FILE)

    state_path = Path(leaf.state_ref)
    artifact_kind = "directory" if state_path.is_dir() else "file"

    existing_actions = [
        {
            "action_id": aid,
            "description": act.description,
            "prior": act.prior,
            "risk": act.risk,
            "expanded": aid in leaf.children,
            "child_visits": engine.nodes[leaf.children[aid]].visit_count if aid in leaf.children else 0,
            "child_q": engine.nodes[leaf.children[aid]].q_value if aid in leaf.children else None,
        }
        for aid, act in leaf.actions.items()
    ]

    target_action_id = None
    action_description = None
    action_prior = None
    action_risk = None
    if needs_moves:
        status = "ready_for_moves"
    elif pending_action_id is not None:
        status = "ready_for_eval"
        target_action_id = pending_action_id
        action_description = leaf.actions[pending_action_id].description
        action_prior = leaf.actions[pending_action_id].prior
        action_risk = leaf.actions[pending_action_id].risk
    else:
        status = "no_actionable_node"

    iterations_done = engine.iterations_done()
    target = engine.target_iterations
    print(json.dumps({
        "status": status,
        "target_node_id": leaf.node_id,
        "target_action_id": target_action_id,
        "action_description": action_description,
        "action_prior": action_prior,
        "action_risk": action_risk,
        "state_ref": leaf.state_ref,
        "artifact_kind": artifact_kind,
        "existing_actions": existing_actions,
        "depth": len(path) - 1,
        "q_value": leaf.q_value,
        "visits": leaf.visit_count,
        "target_batch_size": engine.batch_size,
        "target_wildness": engine.wildness,
        **stats_block(engine)
    }))


def cmd_record(args):
    engine = get_engine()
    if args.node_id not in engine.nodes:
        raise ValueError(f"Target node {args.node_id} not found in search tree.")
    parent = engine.nodes[args.node_id]

    if args.action_id:
        if args.action_id not in parent.actions:
            raise ValueError(f"Action {args.action_id} not found on node {args.node_id}. Propose it first.")
        if args.action_id in parent.children:
            raise ValueError(
                f"Action {args.action_id} on node {args.node_id} is already expanded "
                f"(child {parent.children[args.action_id]})."
            )
        action_id = args.action_id
    else:
        # Fallback: ad hoc single move, not part of a batch proposal. Not
        # normalized against siblings — prefer `propose` + `--action-id`.
        desc = args.desc
        if args.desc_file:
            desc = Path(args.desc_file).read_text()
        if not desc or args.prior is None:
            raise ValueError(
                "Must supply --action-id (from a proposed batch) or both --prior and a "
                "description (--desc, or --desc-file to avoid shell-quoting issues) for an "
                "ad hoc move."
            )
        action_id = f"act_{len(parent.actions) + 1}"
        parent.actions[action_id] = Action(
            action_id=action_id, description=desc, prior=args.prior, risk=args.risk or "bold"
        )

    new_node_id = engine.next_id()
    new_state_ref = ARTIFACTS_DIR / f"{new_node_id}.state"
    artifact_kind = copy_state(Path(args.new_state_path), new_state_ref)

    child_node = MCTSNode(
        node_id=new_node_id,
        state_ref=str(new_state_ref),
        parent_id=parent.node_id,
        incoming_action=action_id,
    )

    parent.children[action_id] = new_node_id
    engine.nodes[new_node_id] = child_node

    next_moves = load_moves(args)
    proposed_action_ids, moves_warning = (
        engine.add_actions(child_node, next_moves) if next_moves else ([], None)
    )

    path = []
    curr = child_node
    while curr:
        path.append(curr)
        curr = engine.nodes.get(curr.parent_id) if curr.parent_id else None
    path.reverse()
    engine.backpropagate(path, args.value)

    engine.save(TREE_FILE)
    iterations_done = engine.iterations_done()
    target = engine.target_iterations
    print(json.dumps({
        "status": "recorded",
        "new_node_id": new_node_id,
        "action_id": action_id,
        "state_ref": str(new_state_ref),
        "artifact_kind": artifact_kind,
        "score": args.value,
        "proposed_action_ids": proposed_action_ids,
        "proposed_moves_warning": moves_warning,
        "target_reached": iterations_done >= target,
        "target_batch_size": engine.batch_size,
        "target_wildness": engine.wildness,
        **stats_block(engine)
    }))


def cmd_best(args):
    engine = get_engine()
    k = args.top

    trajectories = []  # (first_child_node_id, trajectory) so sibling candidates stay comparable

    def walk(start):
        trajectory = []
        curr = start
        while curr:
            sp = Path(curr.state_ref)

            desc = "ROOT"
            risk = None
            if curr.incoming_action and curr.parent_id:
                parent = engine.nodes[curr.parent_id]
                desc = parent.actions[curr.incoming_action].description
                risk = parent.actions[curr.incoming_action].risk

            trajectory.append({
                "node_id": curr.node_id,
                "action": desc,
                "risk": risk,
                "q_value": curr.q_value,
                "visits": curr.visit_count,
                "state_ref": curr.state_ref,
                "artifact_kind": "directory" if sp.is_dir() else "file"
            })

            if not curr.children:
                break
            curr = max(
                [engine.nodes[cid] for cid in curr.children.values()],
                key=lambda node: node.visit_count
            )
        return trajectory

    # Candidate roots: each expanded child of the search root defines one
    # top-level "concept" (a distinct first move). Walk each concept's
    # robust-child trajectory; rank concepts by leaf visit count, tie-break on Q.
    if not engine.root_id or engine.root_id not in engine.nodes:
        raise ValueError("Search tree has no root; run init first.")
    root = engine.nodes[engine.root_id]
    first_children = sorted(
        (engine.nodes[cid] for cid in root.children.values()),
        key=lambda n: (n.visit_count, n.q_value),
        reverse=True,
    )

    for child in first_children:
        traj = walk(child)
        # Prepend the shared root context.
        root_entry = {
            "node_id": root.node_id,
            "action": "ROOT",
            "risk": None,
            "q_value": root.q_value,
            "visits": root.visit_count,
            "state_ref": root.state_ref,
            "artifact_kind": "directory" if Path(root.state_ref).is_dir() else "file"
        }
        traj = [root_entry] + traj
        leaf = traj[-1]
        trajectories.append({
            "concept": traj[1]["action"],
            "final_q_value": leaf["q_value"],
            "final_visits": leaf["visits"],
            "depth": len(traj) - 1,
            "subtree_nodes": engine.subtree_size(child.node_id),
            "subtree_depth": engine.subtree_max_depth(child.node_id),
            "trajectory": traj
        })

    # Rank by the leaf's visit count (robust-child rule), tie-break on Q.
    trajectories.sort(key=lambda t: (t["final_visits"], t["final_q_value"]), reverse=True)
    top = trajectories[:k]

    print(json.dumps({
        "top_concepts": [
            {
                "rank": i + 1,
                "concept": t["concept"],
                "final_q_value": t["final_q_value"],
                "final_visits": t["final_visits"],
                "depth": t["depth"],
                "subtree_nodes": t["subtree_nodes"],
                "subtree_depth": t["subtree_depth"],
                "leaf_state_ref": t["trajectory"][-1]["state_ref"],
                "trajectory": t["trajectory"]
            }
            for i, t in enumerate(top)
        ],
        "iterations_done": engine.iterations_done(),
        "target_iterations": engine.target_iterations,
        "total_nodes": len(engine.nodes),
        "tree_max_depth": engine.tree_max_depth(),
        "root_children": engine.root_children_stats(top_n=None)
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init")
    p_init.add_argument(
        "--state-file", type=str, required=True,
        help="Path to a file or directory containing the artifact to refine (required). "
             "Inline text is not accepted — the artifact must be specified by path."
    )
    p_init.add_argument("--iterations", type=int, default=100)
    p_init.add_argument(
        "--force-restart", action="store_true",
        help="Explicitly discard an existing .mcts_tree.json/.mcts_artifacts and start a fresh "
             "search. init otherwise refuses to run when a tree already exists — never use this "
             "to 'add' nodes; it deletes ALL prior refinement work."
    )
    p_init.add_argument(
        "--batch-size", type=int, default=4,
        help="Target number of candidate moves to propose per node (default 4). A reminder echoed "
             "in every step/propose/record response — the agent still generates each batch by hand."
    )
    p_init.add_argument(
        "--wildness", type=float, default=0.25,
        help="Target fraction, in [0,1], of each move batch that should be tagged \"risk\":\"wild\" "
             "(experimental/long-shot moves) rather than \"safe\"/\"bold\" (default 0.25). Batches of "
             ">= 3 moves with zero \"wild\" entries get a nudge warning when this is > 0."
    )
    p_init.add_argument("--moves", type=str, default=None, help='JSON list: [{"desc": "...", "prior": 0.3, "risk": "bold"}, ...]')
    p_init.add_argument("--moves-file", type=str, default=None)

    sub.add_parser("step")

    p_propose = sub.add_parser("propose")
    p_propose.add_argument("--node-id", required=True)
    p_propose.add_argument("--moves", type=str, default=None, help='JSON list: [{"desc": "...", "prior": 0.3, "risk": "bold"}, ...]')
    p_propose.add_argument("--moves-file", type=str, default=None)

    p_record = sub.add_parser("record")
    p_record.add_argument("--node-id", required=True)
    p_record.add_argument("--action-id", default=None, help="A stub action from step/propose to realize.")
    p_record.add_argument("--desc", default=None, help="Ad hoc move (fallback if --action-id is omitted).")
    p_record.add_argument(
        "--desc-file", default=None,
        help="Read the ad hoc move description from a file instead of --desc, to avoid shell "
             "quoting problems when the text contains quotes/apostrophes/special characters."
    )
    p_record.add_argument("--prior", type=float, default=None, help="Ad hoc move prior (fallback).")
    p_record.add_argument("--risk", default=None, choices=["safe", "bold", "wild"], help="Ad hoc move risk tag (fallback).")
    p_record.add_argument(
        "--new-state-path", type=str, required=True,
        help="Path to the edited artifact (file or directory, matching the root artifact's kind). "
             "Inline text is not accepted — write the edited artifact to disk yourself first."
    )
    p_record.add_argument("--value", type=float, required=True)
    p_record.add_argument("--moves", type=str, default=None, help='Batch of moves to propose on the new child: [{"desc": "...", "prior": 0.3, "risk": "bold"}, ...]')
    p_record.add_argument("--moves-file", type=str, default=None)

    p_best = sub.add_parser("best")
    p_best.add_argument(
        "--top", type=int, default=3,
        help="Number of distinct top-level concepts (root's most-visited first moves) to return, "
             "each as its own best trajectory ranked by robust-child visits (default 3)."
    )

    args = parser.parse_args()
    cmds = {
        "init": cmd_init,
        "step": cmd_step,
        "propose": cmd_propose,
        "record": cmd_record,
        "best": cmd_best,
    }
    if args.command in cmds:
        cmds[args.command](args)
