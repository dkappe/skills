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
    return JsonMCTSEngine()


def cmd_init(args):
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    engine = JsonMCTSEngine()

    root_state_ref = ARTIFACTS_DIR / "n_0.state"
    if args.state_file:
        shutil.copy(args.state_file, root_state_ref)
    else:
        root_state_ref.write_text(args.state or "")

    root_node = MCTSNode(node_id="n_0", state_ref=str(root_state_ref))
    engine.root_id = "n_0"
    engine.nodes["n_0"] = root_node
    engine.save(TREE_FILE)

    print(json.dumps({
        "status": "initialized",
        "root_id": "n_0",
        "state_ref": str(root_state_ref)
    }))


def cmd_step(args):
    engine = get_engine()
    path, needs_expansion = engine.select()
    leaf = path[-1]
    engine.save(TREE_FILE)

    state_content = ""
    state_path = Path(leaf.state_ref)
    if state_path.exists():
        state_content = state_path.read_text(errors="replace")

    print(json.dumps({
        "status": "ready_for_expansion" if needs_expansion else "ready_for_eval",
        "target_node_id": leaf.node_id,
        "state_ref": leaf.state_ref,
        "state_content": state_content,
        "existing_actions": [a.description for a in leaf.actions.values()],
        "depth": len(path) - 1,
        "q_value": leaf.q_value,
        "visits": leaf.visit_count
    }))


def cmd_record(args):
    engine = get_engine()
    if args.node_id not in engine.nodes:
        raise ValueError(f"Target node {args.node_id} not found in search tree.")

    parent = engine.nodes[args.node_id]
    new_node_id = engine.next_id()
    new_state_ref = ARTIFACTS_DIR / f"{new_node_id}.state"

    if args.new_state_file:
        shutil.copy(args.new_state_file, new_state_ref)
    else:
        new_state_ref.write_text(args.new_state or "")

    action_id = f"act_{len(parent.actions) + 1}"
    action = Action(action_id=action_id, description=args.desc, prior=args.prior)

    child_node = MCTSNode(
        node_id=new_node_id,
        state_ref=str(new_state_ref),
        parent_id=parent.node_id,
        incoming_action=action_id,
    )

    parent.children[action_id] = new_node_id
    parent.actions[action_id] = action
    engine.nodes[new_node_id] = child_node

    path = []
    curr = child_node
    while curr:
        path.append(curr)
        curr = engine.nodes.get(curr.parent_id) if curr.parent_id else None
    path.reverse()
    engine.backpropagate(path, args.value)

    engine.save(TREE_FILE)
    print(json.dumps({
        "status": "recorded",
        "new_node_id": new_node_id,
        "state_ref": str(new_state_ref),
        "score": args.value
    }))


def cmd_best(args):
    engine = get_engine()
    curr = engine.nodes[engine.root_id]
    trajectory = []

    while curr:
        state_content = ""
        sp = Path(curr.state_ref)
        if sp.exists():
            state_content = sp.read_text(errors="replace")

        desc = "ROOT"
        if curr.incoming_action and curr.parent_id:
            parent = engine.nodes[curr.parent_id]
            desc = parent.actions[curr.incoming_action].description

        trajectory.append({
            "node_id": curr.node_id,
            "action": desc,
            "q_value": curr.q_value,
            "visits": curr.visit_count,
            "state_ref": curr.state_ref,
            "state_content": state_content
        })

        if not curr.children:
            break
        curr = max(
            [engine.nodes[cid] for cid in curr.children.values()],
            key=lambda node: node.visit_count
        )

    print(json.dumps({"best_trajectory": trajectory}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init")
    p_init.add_argument("--state", type=str, default="")
    p_init.add_argument("--state-file", type=str, default=None)

    sub.add_parser("step")

    p_record = sub.add_parser("record")
    p_record.add_argument("--node-id", required=True)
    p_record.add_argument("--desc", required=True)
    p_record.add_argument("--prior", type=float, required=True)
    p_record.add_argument("--new-state", type=str, default="")
    p_record.add_argument("--new-state-file", type=str, default=None)
    p_record.add_argument("--value", type=float, required=True)

    sub.add_parser("best")

    args = parser.parse_args()
    cmds = {"init": cmd_init, "step": cmd_step, "record": cmd_record, "best": cmd_best}
    if args.command in cmds:
        cmds[args.command](args)
