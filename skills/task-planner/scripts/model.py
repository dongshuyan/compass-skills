"""The plan tree, prerequisites and observable units of work."""
from __future__ import annotations

from graphlib import CycleError, TopologicalSorter
import math
import re


class Invalid(ValueError):
    """A document or event cannot be applied as written."""


class Conflict(Invalid):
    """The caller needs a fresh view of the current plan."""


def require(condition, message):
    if not condition:
        raise Invalid(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def number(value):
    return type(value) in (float, int) and math.isfinite(value)


def strings(value, field, *, required=False):
    require(isinstance(value, list) and all(text(item) for item in value), f"{field}: expected a list of text")
    require(not required or value, f"{field}: specify observable evidence")


def fields(obj, required, optional=()):
    require(isinstance(obj, dict), "expected a JSON object")
    missing = set(required) - obj.keys()
    extra = obj.keys() - set(required) - set(optional)
    require(not missing, "missing fields: " + ", ".join(sorted(missing)))
    require(not extra, "unknown fields: " + ", ".join(sorted(extra)))


def estimate(value):
    bounds = value if isinstance(value, list) else [value, value]
    require(len(bounds) == 2 and all(number(x) for x in bounds) and 0 < bounds[0] <= bounds[1],
            "estimate_minutes: use positive minutes or [low, high]")
    return bounds


def dependency(value):
    if isinstance(value, str):
        return value, "passed"
    fields(value, ("id", "needs"))
    require(text(value["id"]) and value["needs"] in ("passed", "evidence"),
            "deps: use a node ID or {id, needs: passed|evidence}")
    return value["id"], value["needs"]


NODE_TEXT = ("title", "description", "deliverable", "expected", "acceptance", "rationale")
NODE_FIELDS = ("id", "parent", *NODE_TEXT, "constraints", "estimate_minutes", "deps", "facts")
FORECAST_FIELDS = {"expected", "estimate_minutes", "facts", "rationale", "baseline"}
PROTECTED_ROOT = {"title", "description", "deliverable", "acceptance", "constraints"}


def has_usable_result(entry):
    result = entry.get("result", {})
    if entry["status"] == "active":
        return False
    return result.get("verdict") == "passed" or (result.get("verdict") == "deviation"
                                                 and bool(result.get("usable_evidence")))


def validate_node(n):
    fields(n, NODE_FIELDS, ("baseline", "awaiting_input"))
    require(text(n["id"]) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", n["id"]),
            "id: use a stable letter/number identifier, optionally with . _ or -")
    require(n["parent"] is None or text(n["parent"]), f"{n['id']}: invalid parent")
    for name in NODE_TEXT:
        require(text(n[name]), f"{n['id']}.{name}: supply plain text")
    strings(n["constraints"], "constraints")
    if n.get("awaiting_input") is not None:
        require(text(n["awaiting_input"]), "awaiting_input: describe the outstanding external input")
    estimate(n["estimate_minutes"])
    require(isinstance(n["deps"], list), "deps: expected a list")
    deps = [dependency(d)[0] for d in n["deps"]]
    require(len(set(deps)) == len(deps), f"{n['id']}: repeated prerequisite")
    require(isinstance(n["facts"], list) and n["facts"], f"{n['id']}: give the basis for the plan")
    for fact in n["facts"]:
        fields(fact, ("claim", "source", "confidence"))
        require(text(fact["claim"]) and fact["confidence"] in ("high", "medium", "low"),
                "facts: each claim has high, medium or low confidence")
        source = fact["source"]
        require(text(source) or (source is None and fact["confidence"] == "low"),
                "facts: name the source, or use null and low confidence")
    baseline = n.get("baseline")
    if baseline is not None:
        fields(baseline, ("metric", "method", "node"), ("use",))
        require(all(text(baseline[k]) for k in ("metric", "method", "node")),
                "baseline: name metric, method and measurement node")
        require(baseline.get("use", "input") in ("input", "forecast"), "baseline.use: use input or forecast")


class Tree:
    def __init__(self, state):
        self.state = state
        self.nodes = {n["id"]: n for n in state["nodes"]}
        self.work = state["work"]
        self.children = {key: [] for key in self.nodes}
        self.live = [key for key in self.nodes if self.work[key]["status"] != "retired"]
        roots = [key for key in self.live if self.nodes[key]["parent"] is None]
        require(len(roots) == 1, "provide exactly one live root node")
        self.root = roots[0]
        for key in self.live:
            parent = self.nodes[key]["parent"]
            if parent is not None:
                require(parent in self.nodes and self.work[parent]["status"] != "retired",
                        f"{key}: unknown or retired parent {parent}")
                self.children[parent].append(key)

    def ancestors(self, key):
        parent = self.nodes[key]["parent"]
        while parent is not None:
            yield parent
            parent = self.nodes[parent]["parent"]

    def direct_dependencies(self, key):
        node = self.nodes[key]
        for dep in node["deps"]:
            yield dependency(dep)
        baseline = node.get("baseline")
        if baseline:
            default = "input" if not self.children[key] and baseline["node"] != key else "forecast"
            if baseline.get("use", default) == "input":
                yield baseline["node"], "evidence"

    def blockers(self, key):
        blocked = []
        for owner in (key, *self.ancestors(key)):
            for target, needs in self.direct_dependencies(owner):
                entry = self.work[target]
                ok = entry["status"] == "passed"
                if needs == "evidence":
                    ok = has_usable_result(entry)
                if not ok and target not in blocked:
                    blocked.append(target)
        return blocked

    def validate(self):
        graph = TopologicalSorter()
        for key in self.live:
            n = self.nodes[key]
            start, end = ("start", key), ("end", key)
            graph.add(end, start)
            if n["parent"] is not None:
                graph.add(start, ("start", n["parent"]))
                graph.add(("end", n["parent"]), end)
            if not self.children[key]:
                require(estimate(n["estimate_minutes"])[1] <= 360, f"{key}: a leaf exceeds six hours")
            else:
                require(not n.get("awaiting_input"), f"{key}: place the external input on a receipt leaf")
            for target, needs in self.direct_dependencies(key):
                require(target in self.nodes, f"{key}: unknown prerequisite {target}")
                if self.work[target]["status"] == "retired":
                    require(needs == "evidence" and has_usable_result(self.work[target]),
                            f"{key}: a retired prerequisite cannot provide this result")
                else:
                    graph.add(start, ("end", target))
            if n.get("baseline"):
                target = n["baseline"]["node"]
                require(target in self.nodes and self.work[target]["status"] != "retired",
                        f"{key}: choose a current measurement node")
        try:
            graph.prepare()
        except CycleError as exc:
            raise Invalid(f"cycle between hierarchy and prerequisites: {exc.args[1]}") from exc

    def status(self):
        pending = [key for key in self.live if self.work[key]["status"] == "planned" and not self.children[key]]
        blocked = {key: causes for key in pending if (causes := self.blockers(key))}
        eligible = [key for key in pending if key not in blocked]
        waiting = {key: self.nodes[key]["awaiting_input"] for key in eligible if self.nodes[key].get("awaiting_input")}
        ready = [key for key in eligible if key not in waiting]
        return {"revision": self.state["revision"], "goal": self.state["goal"], "root": self.root,
                "ready": ready, "awaiting_input": waiting, "blocked": blocked,
                "active": [k for k in self.live if self.work[k]["status"] == "active"],
                "interrupted": [k for k in self.live if self.work[k]["status"] == "interrupted"],
                "awaiting_acceptance": [k for k in self.live if self.children[k]
                    and self.work[k]["status"] == "active"
                    and all(self.work[c]["status"] == "passed" for c in self.children[k])],
                "deviations": [k for k in self.live if self.work[k]["status"] == "deviation"]}


def validate(state):
    require(isinstance(state["nodes"], list) and state["nodes"], "a plan needs at least one node")
    for node in state["nodes"]:
        validate_node(node)
    ids = [n["id"] for n in state["nodes"]]
    require(len(ids) == len(set(ids)), "node IDs must be unique")
    require(set(ids) == state["work"].keys(), "node definitions and result records disagree")
    tree = Tree(state)
    tree.validate()
    return tree
