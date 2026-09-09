import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class Action:
    def __init__(self, action_id: str, description: str, prior: float, diff_ref: Optional[str] = None):
        self.action_id = action_id
        self.description = description
        self.prior = float(prior)
        self.diff_ref = diff_ref

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "description": self.description,
            "prior": self.prior,
            "diff_ref": self.diff_ref,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Action":
        return cls(
            action_id=data["action_id"],
            description=data["description"],
            prior=data["prior"],
            diff_ref=data.get("diff_ref"),
        )


class MCTSNode:
    def __init__(
        self,
        node_id: str,
        state_ref: str,
        parent_id: Optional[str] = None,
        incoming_action: Optional[str] = None,
    ):
        self.node_id = node_id
        self.state_ref = state_ref
        self.parent_id = parent_id
        self.incoming_action = incoming_action

        self.visit_count: int = 0
        self.value_sum: float = 0.0
        self.q_value: float = 0.0
        self.is_terminal: bool = False
        self.children: Dict[str, str] = {}
        self.actions: Dict[str, Action] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "state_ref": self.state_ref,
            "parent_id": self.parent_id,
            "incoming_action": self.incoming_action,
            "visit_count": self.visit_count,
            "value_sum": self.value_sum,
            "q_value": self.q_value,
            "is_terminal": self.is_terminal,
            "children": self.children,
            "actions": {aid: act.to_dict() for aid, act in self.actions.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCTSNode":
        node = cls(
            node_id=data["node_id"],
            state_ref=data["state_ref"],
            parent_id=data.get("parent_id"),
            incoming_action=data.get("incoming_action"),
        )
        node.visit_count = data["visit_count"]
        node.value_sum = data["value_sum"]
        node.q_value = data["q_value"]
        node.is_terminal = data.get("is_terminal", False)
        node.children = data.get("children", {})
        node.actions = {aid: Action.from_dict(act) for aid, act in data.get("actions", {}).items()}
        return node


class JsonMCTSEngine:
    def __init__(
        self,
        c_puct: float = 1.414,
        widening_c: float = 1.5,
        widening_alpha: float = 0.5,
        max_depth: int = 0,
    ):
        self.c_puct = c_puct
        self.widening_c = widening_c
        self.widening_alpha = widening_alpha
        self.max_depth = max_depth
        self.nodes: Dict[str, MCTSNode] = {}
        self.root_id: Optional[str] = None
        self._node_counter: int = 0

    def next_id(self) -> str:
        self._node_counter += 1
        return f"n_{self._node_counter}"

    def should_widen(self, node: MCTSNode) -> bool:
        allowed = math.floor(self.widening_c * (node.visit_count ** self.widening_alpha))
        return len(node.children) < max(1, allowed)

    def select(self) -> Tuple[List[MCTSNode], bool]:
        if self.root_id is None:
            raise ValueError("Search tree has no root; call init first.")
        path = [self.nodes[self.root_id]]
        while (
            path[-1].children
            and not path[-1].is_terminal
            and (self.max_depth <= 0 or len(path) <= self.max_depth)
        ):
            curr = path[-1]
            if self.should_widen(curr):
                return path, True

            best_aid = max(
                curr.children.keys(),
                key=lambda aid: (
                    self.nodes[curr.children[aid]].q_value
                    + self.c_puct
                    * curr.actions[aid].prior
                    * (math.sqrt(curr.visit_count) / (1.0 + self.nodes[curr.children[aid]].visit_count))
                ),
            )
            path.append(self.nodes[curr.children[best_aid]])

        return path, len(path[-1].children) == 0

    def backpropagate(self, path: List[MCTSNode], value: float) -> None:
        for node in reversed(path):
            node.visit_count += 1
            node.value_sum += value
            node.q_value = node.value_sum / node.visit_count

    def save(self, filepath: Path) -> None:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "meta": {
                "c_puct": self.c_puct,
                "widening_c": self.widening_c,
                "widening_alpha": self.widening_alpha,
                "max_depth": self.max_depth,
                "node_counter": self._node_counter,
            },
            "root_id": self.root_id,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: Path) -> "JsonMCTSEngine":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta = data.get("meta", {})
        engine = cls(
            c_puct=meta.get("c_puct", 1.414),
            widening_c=meta.get("widening_c", 1.5),
            widening_alpha=meta.get("widening_alpha", 0.5),
            max_depth=meta.get("max_depth", 0),
        )
        engine._node_counter = meta.get("node_counter", 0)
        engine.root_id = data.get("root_id")
        engine.nodes = {nid: MCTSNode.from_dict(ndata) for nid, ndata in data.get("nodes", {}).items()}
        return engine
