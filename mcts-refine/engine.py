import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


RISK_LEVELS = ("safe", "bold", "wild")


class Action:
    def __init__(
        self,
        action_id: str,
        description: str,
        prior: float,
        diff_ref: Optional[str] = None,
        risk: str = "bold",
    ):
        self.action_id = action_id
        self.description = description
        self.prior = float(prior)
        self.diff_ref = diff_ref
        self.risk = risk if risk in RISK_LEVELS else "bold"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "description": self.description,
            "prior": self.prior,
            "diff_ref": self.diff_ref,
            "risk": self.risk,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Action":
        return cls(
            action_id=data["action_id"],
            description=data["description"],
            prior=data["prior"],
            diff_ref=data.get("diff_ref"),
            risk=data.get("risk", "bold"),
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
        target_iterations: int = 100,
        batch_size: int = 4,
        wildness: float = 0.25,
        max_change_fraction: float = 0.4,
    ):
        self.c_puct = c_puct
        self.widening_c = widening_c
        self.widening_alpha = widening_alpha
        self.max_depth = max_depth
        self.target_iterations = target_iterations
        self.batch_size = batch_size
        self.wildness = wildness
        self.max_change_fraction = max_change_fraction
        self.nodes: Dict[str, MCTSNode] = {}
        self.root_id: Optional[str] = None
        self._node_counter: int = 0

    def next_id(self) -> str:
        self._node_counter += 1
        return f"n_{self._node_counter}"

    def iterations_done(self) -> int:
        return max(0, len(self.nodes) - 1)

    def depth_of(self, node_id: str) -> int:
        depth = 0
        curr = self.nodes.get(node_id)
        while curr and curr.parent_id:
            depth += 1
            curr = self.nodes.get(curr.parent_id)
        return depth

    def tree_max_depth(self) -> int:
        if not self.nodes:
            return 0
        return max(self.depth_of(nid) for nid in self.nodes)

    def subtree_size(self, node_id: str) -> int:
        """Total node count of the subtree rooted at node_id (inclusive)."""
        total = 0
        stack = [node_id]
        while stack:
            node = self.nodes.get(stack.pop())
            if node is None:
                continue
            total += 1
            stack.extend(node.children.values())
        return total

    def subtree_max_depth(self, node_id: str) -> int:
        """Deepest absolute depth (root = 0) within the subtree rooted at node_id."""
        best = self.depth_of(node_id)
        stack = [(node_id, best)]
        while stack:
            nid, d = stack.pop()
            node = self.nodes.get(nid)
            if node is None:
                continue
            best = max(best, d)
            for cid in node.children.values():
                stack.append((cid, d + 1))
        return best

    def root_children_stats(self, top_n: Optional[int] = 3) -> List[Dict[str, Any]]:
        """LC0-style policy readout over the root's candidate moves, ranked by
        visit count (tie-break Q, then prior). Pure tree bookkeeping: stub
        (unexpanded) actions report zero visits so the full candidate set and
        its priors stay visible. top_n caps the returned list (None = all
        root moves, as in the final 'best' report). No artifact content is
        ever touched."""
        root = self.nodes.get(self.root_id) if self.root_id else None
        if root is None:
            return []
        entries = []
        for aid, act in root.actions.items():
            child_id = root.children.get(aid)
            child = self.nodes.get(child_id) if child_id else None
            entries.append({
                "action_id": aid,
                "desc": act.description,
                "prior": act.prior,
                "risk": act.risk,
                "expanded": child is not None,
                "child_id": child_id,
                "visits": child.visit_count if child else 0,
                "q_value": child.q_value if child else None,
                "subtree_nodes": self.subtree_size(child_id) if child_id else 0,
                "subtree_depth": self.subtree_max_depth(child_id) if child_id else 0,
            })
        entries.sort(
            key=lambda e: (
                e["visits"],
                e["q_value"] if e["q_value"] is not None else float("-inf"),
                e["prior"],
            ),
            reverse=True,
        )
        if top_n is not None:
            entries = entries[:top_n]
        return entries

    def add_actions(self, node: MCTSNode, moves: List[Dict[str, Any]]) -> Tuple[List[str], Optional[str]]:
        """Register a batch of candidate moves (description + prior + optional
        risk) on a node as unexpanded ("stub") actions — no child node/state/
        value yet, matching an AlphaZero-style policy-head output. Priors are
        expected to sum to 1.0 across the batch; if they don't (within 1e-3),
        they are normalized and a warning is returned (normalize-and-warn, not
        a hard rejection).

        Each move may carry a "risk" tag — one of "safe" (incremental,
        high-confidence), "bold" (default; a real structural change), or
        "wild" (long-shot, experimental, break-the-mold). This is bookkeeping
        only: the harness never generates moves itself, so it can't enforce a
        risk mix, but it will nudge with a warning if a sizeable batch has zero
        "wild" entries while the engine's configured `wildness` target is > 0.
        """
        if not moves:
            return [], None

        parsed = [
            {
                "desc": m["desc"],
                "prior": float(m["prior"]),
                "risk": m.get("risk", "bold") if m.get("risk") in RISK_LEVELS else "bold",
            }
            for m in moves
        ]
        total = sum(m["prior"] for m in parsed)
        warnings: List[str] = []
        epsilon = 1e-3

        if abs(total - 1.0) > epsilon:
            if total <= 0:
                n = len(parsed)
                for m in parsed:
                    m["prior"] = 1.0 / n
                warnings.append(
                    f"Priors summed to {total:.4f} (<= 0); could not scale, "
                    f"reset to uniform 1/{n} each instead."
                )
            else:
                for m in parsed:
                    m["prior"] = m["prior"] / total
                warnings.append(
                    f"Priors summed to {total:.4f}, not 1.0 (+/- {epsilon}); "
                    f"normalized by dividing each by {total:.4f}."
                )

        wild_count = sum(1 for m in parsed if m["risk"] == "wild")
        if self.wildness > 0 and len(parsed) >= 3 and wild_count == 0:
            expected = max(1, round(len(parsed) * self.wildness))
            warnings.append(
                f"No move in this batch of {len(parsed)} was tagged \"wild\", but the configured "
                f"wildness is {self.wildness:.2f} (~{expected} wild move(s) expected per batch of this "
                f"size). Consider adding a higher-risk/experimental option."
            )

        action_ids = []
        for m in parsed:
            action_id = f"act_{len(node.actions) + 1}"
            node.actions[action_id] = Action(
                action_id=action_id, description=m["desc"], prior=m["prior"], risk=m["risk"]
            )
            action_ids.append(action_id)
        return action_ids, ("; ".join(warnings) if warnings else None)

    def select(self) -> Tuple[List[MCTSNode], Optional[str], bool]:
        """Walk down the tree via PUCT over a node's full action set (expanded
        children AND unexpanded stub actions treated as q=0/visits=0, i.e. First
        Play Urgency) — mirroring how AlphaZero selects among all known policy
        edges, not just already-visited ones.

        Returns (path, pending_action_id, needs_moves):
        - needs_moves=True: path[-1] has no actions registered yet; the caller
          must propose a batch of moves (with priors) for it before anything can
          be expanded.
        - pending_action_id set: PUCT chose an unexpanded stub action on
          path[-1]; the caller should realize it (generate state + value).
        - both falsy: path[-1] is terminal or depth-capped with nothing left to
          do.
        """
        if self.root_id is None:
            raise ValueError("Search tree has no root; call init first.")
        path = [self.nodes[self.root_id]]
        while True:
            curr = path[-1]
            if curr.is_terminal:
                return path, None, False
            if self.max_depth > 0 and len(path) > self.max_depth:
                return path, None, False
            if not curr.actions:
                return path, None, True

            def score(aid: str) -> float:
                act = curr.actions[aid]
                child_id = curr.children.get(aid)
                if child_id is not None:
                    child = self.nodes[child_id]
                    q, n = child.q_value, child.visit_count
                else:
                    q, n = 0.0, 0
                return q + self.c_puct * act.prior * (math.sqrt(curr.visit_count) / (1.0 + n))

            best_aid = max(curr.actions.keys(), key=score)
            child_id = curr.children.get(best_aid)
            if child_id is None:
                return path, best_aid, False
            path.append(self.nodes[child_id])

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
                "target_iterations": self.target_iterations,
                "batch_size": self.batch_size,
                "wildness": self.wildness,
                "max_change_fraction": self.max_change_fraction,
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
            target_iterations=meta.get("target_iterations", 100),
            batch_size=meta.get("batch_size", 4),
            wildness=meta.get("wildness", 0.25),
            max_change_fraction=meta.get("max_change_fraction", 0.4),
        )
        engine._node_counter = meta.get("node_counter", 0)
        engine.root_id = data.get("root_id")
        engine.nodes = {nid: MCTSNode.from_dict(ndata) for nid, ndata in data.get("nodes", {}).items()}
        return engine
