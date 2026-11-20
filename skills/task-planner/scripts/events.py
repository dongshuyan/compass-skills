"""Commit one observed transition and its associated plan corrections."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import uuid

from model import (Conflict, FORECAST_FIELDS, Invalid, NODE_FIELDS, PROTECTED_ROOT, Tree, estimate, fields,
                   number, require, strings, text, validate, validate_node)


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def digest(value):
    encoded = json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def initialize(spec):
    fields(spec, ("title", "goal", "nodes"), ("lang", "labels"))
    require(text(spec["title"]) and text(spec["goal"]), "provide a title and the confirmed goal")
    lang = spec.get("lang", "zh-CN")
    require(text(lang), "lang: use a language tag")
    labels = spec.get("labels", {})
    require(isinstance(labels, dict) and all(text(x) for x in labels.values()), "labels: expected text labels")
    require(isinstance(spec["nodes"], list), "nodes: expected a list")
    for n in spec["nodes"]:
        validate_node(n)
    now = timestamp()
    state = {**spec, "format": "task-planner/1", "uid": uuid.uuid4().hex, "revision": 1,
             "lang": lang, "updated": now, "risk": "", "work": {n["id"]: {"status": "planned"} for n in spec["nodes"]},
             "history": [{"kind": "init", "revision": 1, "time": now, "goal": spec["goal"]}]}
    validate(state)
    return state


def start(tree, key, event, now, record):
    require(tree.work[key]["status"] in ("planned", "deviation", "interrupted"), f"{key}: already started or closed")
    blocked = tree.blockers(key)
    require(not blocked, f"{key}: awaiting prerequisites {', '.join(blocked)}")
    expected_input = tree.nodes[key].get("awaiting_input")
    receipt = event.get("input_evidence")
    if expected_input:
        receipt = receipt or tree.work[key].get("input_evidence")
        require(text(receipt), f"{key}: give input_evidence for the outstanding input")
        record.update(awaiting_input=expected_input, input_evidence=receipt)
        tree.work[key]["input_evidence"] = receipt
    else:
        require("input_evidence" not in event, "input_evidence belongs to an external-input receipt")
    opened = []
    for item in [*reversed(list(tree.ancestors(key))), key]:
        w = tree.work[item]
        require(w["status"] in ("planned", "active", "deviation", "interrupted"), f"{item}: phase is already closed")
        if w["status"] != "active":
            w.update(status="active", started=now, forecast_on_start=deepcopy(tree.nodes[item]))
            opened.append(item)
    record["opened"] = opened


def change_nodes(state, tree, edits, *, agreed):
    require(isinstance(edits, list), "changes: expected a list")
    audit = []
    for edit in edits:
        require(isinstance(edit, dict), "change: expected an object")
        if "add" in edit:
            fields(edit, ("add",))
            node = edit["add"]
            validate_node(node)
            key = node["id"]
            require(key not in tree.nodes, f"{key}: node ID already used")
            require(node["parent"] is not None, "a new node needs a parent")
            state["nodes"].append(node)
            tree.nodes[key] = node
            tree.work[key] = {"status": "planned"}
            audit.append({"op": "add", "id": key, "after": deepcopy(node)})
        elif "edit" in edit:
            fields(edit, ("edit", "set"))
            key, patch = edit["edit"], edit["set"]
            require(text(key) and key in tree.nodes, "edit: unknown node")
            require(isinstance(patch, dict) and patch, "edit: give fields to update")
            require(set(patch) <= (set(NODE_FIELDS) | {"baseline", "awaiting_input"}) - {"id"}, "edit: unknown or immutable field")
            is_root_decision = agreed and key == tree.root
            status = tree.work[key]["status"]
            active_forecast = status == "active" and set(patch) <= FORECAST_FIELDS
            require(status == "planned" or active_forecast or is_root_decision,
                    f"{key}: only forecasts of active work or definitions of future work can be revised")
            if key == tree.root:
                require("parent" not in patch, "the root must stay the root")
                require(is_root_decision or not (set(patch) & PROTECTED_ROOT),
                        "changing the agreed root criteria requires goal_change")
            node = tree.nodes[key]
            if status == "active":
                tree.work[key].setdefault("forecast_on_start", deepcopy(node))
            old = {k: deepcopy(node.get(k)) for k in patch}
            node.update(patch)
            audit.append({"op":"edit", "id":key, "before":old, "after":deepcopy(patch)})
        else:
            fields(edit, ("retire",))
            key = edit["retire"]
            require(text(key) and key in tree.nodes and key != tree.root, "retire: choose a non-root node")
            w = tree.work[key]
            require(w["status"] in ("planned", "deviation", "interrupted"), f"{key}: cannot retire active or passed work")
            audit.append({"op":"retire", "id":key, "before":deepcopy(tree.nodes[key])})
            w["status"] = "retired"
    return audit


def close(state, tree, key, event, now, record):
    w = tree.work[key]
    require(w["status"] == "active", f"{key}: start the node before closing it")
    verdict = event["verdict"]
    require(verdict in ("passed", "deviation", "interrupted"), "verdict: use passed, deviation or interrupted")
    for name in ("actual", "use", "test"):
        require(text(event[name]), f"{name}: describe the observed result or user instructions")
    strings(event["evidence"], "evidence", required=True)
    usable = event.get("usable_evidence")
    if "usable_evidence" in event:
        require(verdict == "deviation" and text(usable),
                "usable_evidence: name the usable result of a deviation and where it was observed")
    require(all(tree.work[c]["status"] != "active" for c in tree.children[key]),
            f"{key}: record active children's outcomes before closing the phase")
    window = (datetime.fromisoformat(now.replace("Z", "+00:00")) -
              datetime.fromisoformat(w["started"].replace("Z", "+00:00"))).total_seconds()
    require(window >= 0 or "duration_seconds" in event, "clock moved backwards: supply an evidenced duration")
    actual_time = event.get("duration_seconds", round(max(0, window), 3))
    require(actual_time is None or (number(actual_time) and actual_time >= 0), "duration_seconds: invalid duration")
    source = event.get("time_source")
    if "duration_seconds" in event or source is not None:
        require(text(source), "time_source: cite the timing record or explain an unknown duration")
    reason = event.get("reason", "")
    require(isinstance(reason, str), "reason: expected text")
    risk = event.get("goal_risk", "")
    require(isinstance(risk, str), "goal_risk: give the evidence and options for the user")
    original = w.get("forecast_on_start", tree.nodes[key])
    limit = min(estimate(n["estimate_minutes"])[1] for n in (original, tree.nodes[key]))
    slow = actual_time is not None and actual_time > limit * 60
    if slow or verdict != "passed" or event.get("changes") or "goal_risk" in event:
        require(text(reason), "reason: explain the deviation, change or goal risk from evidence")
    result = {name:event[name] for name in ("verdict", "actual", "evidence", "use", "test")}
    result.update(duration_seconds=actual_time, time_source=source, window_seconds=round(window, 3),
                  reason=reason, goal_risk=risk, started=w["started"], ended=now)
    if usable:
        result["usable_evidence"] = usable
    record["forecast"] = deepcopy(original)
    w.pop("forecast_on_start", None)
    record["result"] = result
    w.update(status=verdict, result=result)
    record["changes"] = change_nodes(state, tree, event.get("changes", []), agreed=False)
    if "goal_risk" in event:
        state["risk"] = risk


def apply_event(state, event):
    base_fields = ("kind", "event_id", "base_revision", "node")
    require(isinstance(event, dict), "event: expected an object")
    kind = event.get("kind")
    if kind == "start":
        fields(event, base_fields, ("input_evidence",))
    elif kind == "close":
        fields(event, (*base_fields, "verdict", "actual", "evidence", "use", "test"),
               ("duration_seconds", "time_source", "reason", "goal_risk", "changes", "usable_evidence"))
    elif kind == "goal_change":
        fields(event, (*base_fields, "goal", "confirmation", "reason"), ("changes",))
    else:
        raise Invalid("kind: use start, close or goal_change")
    require(text(event["event_id"]), "event_id: provide a unique operation ID")
    signature = digest(event)
    for old in reversed(state["history"]):
        if event["event_id"] == old.get("event_id"):
            require(old["signature"] == signature, "event_id reused for different data")
            return old["revision"], False
    require(type(event["base_revision"]) is int, "base_revision: expected an integer")
    if event["base_revision"] != state["revision"]:
        raise Conflict(f"stale revision, current revision is {state['revision']}; read status and reconcile")
    tree = Tree(state)
    key = event["node"]
    require(text(key) and key in tree.live, f"unknown or retired node: {key}")
    now = timestamp()
    revision = state["revision"] + 1
    record = dict(kind=kind, node=key, time=now, revision=revision, event_id=event["event_id"], signature=signature)
    if kind == "start":
        start(tree, key, event, now, record)
    elif kind == "close":
        close(state, tree, key, event, now, record)
    else:
        require(key == tree.root, "goal_change must address the root")
        require(all(text(event[k]) for k in ("goal", "confirmation", "reason")),
                "supply the user's own decision, the new goal and why it changed")
        require(tree.work[key]["status"] in ("planned","active","deviation","interrupted"),
                "start a new plan for work after a completed goal")
        record.update(before_goal=state["goal"], after_goal=event["goal"],
                      confirmation=event["confirmation"], reason=event["reason"])
        state["goal"] = event["goal"]
        state["risk"] = ""
        record["changes"] = change_nodes(state, tree, event.get("changes", []), agreed=True)
    updated = validate(state)
    # Check the revised tree: a close may retire or replace pending work in the same event.
    for child in updated.live:
        parent = updated.nodes[child]["parent"]
        if parent and updated.work[parent]["status"] == "passed":
            require(updated.work[child]["status"] == "passed",
                    f"{parent}: resolve outstanding children before passing the phase")
    state.update(revision=revision, updated=now)
    state["history"].append(record)
    return revision, True
