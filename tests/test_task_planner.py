"""Exercise the public task-plan commands and the HTML they publish."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1] / "skills" / "task-planner"
CLI = SKILL / "scripts" / "plan.py"


def node(key, parent=None, minutes=10, deps=None):
    return {
        "id": key, "parent": parent, "title": "验收 " + key,
        "description": "核对这次交付。", "constraints": [], "estimate_minutes": minutes,
        "deliverable": "可复测的结果", "expected": "结果与输入一致",
        "acceptance": "重新测量并对照输入", "deps": deps or [],
        "facts": [{"claim": "用户已确认交付目标", "source": "本次需求", "confidence": "high"}],
        "rationale": "与输入核对可验证结果。",
    }


def plan(nodes):
    return {"title": "样本核对", "goal": "交付可复测的结果", "lang": "zh-CN", "nodes": nodes}


def close_fields(verdict="passed"):
    return dict(verdict=verdict, actual="实际完成一次独立核对", evidence=["运行记录 #1"],
                use="打开交付文件", test="用同一组输入再次核对", reason="已核对记录")


class PublicCommands(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.html = self.folder / "计划.html"

    def call(self, cmd, obj=None, ok=True):
        args = [sys.executable, str(CLI), cmd, str(self.html)]
        if obj is not None:
            args.append("-")
        if cmd == "status":
            args.append("--full")
        result = subprocess.run(args, input=json.dumps(obj), capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, (result.stdout, result.stderr))
        return result

    def state(self):
        return json.loads(self.call("status").stdout)

    def event(self, kind, key, **data):
        rev = self.state()["revision"]
        return dict(kind=kind, node=key, event_id=f"test-{rev}-{key}", base_revision=rev, **data)

    def test_single_node_in_progress_then_verified_in_same_file(self):
        self.call("init", plan([node("one", minutes=[1, 360])]))
        self.call("apply", self.event("start", "one"))
        self.assertEqual(self.state()["work"]["one"]["status"], "active")
        event = self.event("close", "one", **close_fields())
        self.call("apply", event)
        original = self.html.read_bytes()
        self.call("apply", event)
        self.assertEqual(original, self.html.read_bytes())
        self.call("apply", dict(event, actual="contradiction"), ok=False)
        result = self.state()["work"]["one"]["result"]
        self.assertEqual(result["verdict"], "passed")
        self.assertGreaterEqual(result["duration_seconds"], 0)

    def test_cycles_with_nested_phases_and_leaf_limit(self):
        self.call("init", plan([node("root", minutes=361)]), ok=False)
        self.call("init", plan([node("P", minutes=400), node("A", "P", deps=["P"])]), ok=False)
        self.call("init", plan([node("P", minutes=400), node("A", "P", deps=["B"]),
                              node("B", "P", deps=["A"])]), ok=False)
        self.call("init", plan([node("P", minutes=400), node("A", "P")]))
        before = self.html.read_bytes()
        self.call("init", plan([node("another")]), ok=False)
        self.assertEqual(before, self.html.read_bytes())

    def test_deviation_and_follow_up_are_published_together(self):
        a, b = node("A", "P"), node("B", "P", deps=["A"])
        self.call("init", plan([node("P"), a, b]))
        self.call("apply", self.event("start", "A"))
        self.call("apply", self.event("close", "P", **close_fields()), ok=False)
        changes = [{"add": node("R", "P", deps=[{"id":"A", "needs":"evidence"}])},
                   {"edit":"B", "set":{"deps":["R"], "estimate_minutes":20}}]
        event = self.event("close", "A", **close_fields("deviation"), changes=changes,
                           usable_evidence="运行记录 #1 中有可复现的错例，可交给修正节点。")
        before = self.html.read_bytes()
        broken = copy.deepcopy(event)
        broken["changes"][1]["set"]["deps"] = ["missing"]
        self.call("apply", broken, ok=False)
        self.assertEqual(self.html.read_bytes(), before)
        self.call("apply", event)
        self.assertEqual(self.state()["revision"], event["base_revision"] + 1)
        self.call("apply", self.event("start","B"), ok=False)
        self.call("apply", self.event("start","R"))
        self.call("apply", self.event("close","R", **close_fields(),
                                     changes=[{"retire":"A"}]))
        self.call("apply", self.event("start","B"))
        self.call("apply", self.event("close","B", **close_fields()))
        self.call("apply", self.event("close","P", **close_fields()))
        state = self.state()
        self.assertEqual(state["work"]["P"]["status"], "passed")
        self.assertEqual(state["goal"], "交付可复测的结果")
        self.assertIn('"R"', json.dumps(state["history"]))

    def test_one_concurrent_writer_wins_then_other_can_retry(self):
        self.call("init", plan([node("P"), node("A", "P"), node("B", "P")]))
        writers = []
        for key in ("A", "B"):
            path = self.folder / (key+".json")
            path.write_text(json.dumps(self.event("start", key)))
            writers.append([sys.executable, str(CLI), "apply", str(self.html), str(path)])
        runs = [subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for args in writers]
        for p in runs:
            p.communicate()
        self.assertEqual(sum(p.returncode == 0 for p in runs), 1)
        state = self.state()
        remaining = next(k for k in ("A", "B") if state["work"][k]["status"] == "planned")
        self.call("apply", self.event("start", remaining))

    def test_goal_requires_a_decision_and_evidence_is_required(self):
        self.call("init", plan([node("P"),node("A","P")]))
        self.call("apply", self.event("start","A"))
        self.call("apply", self.event("close","A", **dict(close_fields(), evidence=[])), ok=False)
        self.call("apply", self.event("close","A", **close_fields(),
                                     changes=[{"edit":"P","set":{"acceptance":"lower bar"}}]), ok=False)
        self.call("apply", self.event("close","A", **close_fields("deviation"),
                                     goal_risk="样本不足以支持目标。可补样本或重新商定门槛。"))
        self.assertEqual(self.state()["goal"], "交付可复测的结果")
        change = self.event("goal_change","P", goal="新达成的目标", reason="用户明确修改约束")
        self.call("apply", change, ok=False)
        self.call("apply", dict(change, confirmation="本次用户决策记录 #2"))
        self.assertEqual(self.state()["goal"], "新达成的目标")

    def test_baseline_and_phase_prerequisites_survive_a_restart(self):
        measure = node("measure", "P")
        phase = node("phase", "P", deps=["measure"])
        later = node("later", "phase")
        later["expected"] = "待首次实测后估算"
        later["baseline"] = {"metric":"正确率","method":"按已确认样本复测","node":"measure"}
        self.call("init", plan([node("P"), measure, phase, later]))
        self.call("apply", self.event("start", "later"), ok=False)
        self.call("apply", self.event("start", "measure"))
        event = self.event("close", "measure", **close_fields(), duration_seconds=None,
                           time_source="承接中断的执行，原始计时不可核实")
        self.call("apply", event)
        self.call("apply", self.event("start", "later"))
        state = self.state()
        self.assertIsNone(state["work"]["measure"]["result"]["duration_seconds"])
        self.assertEqual(state["work"]["phase"]["status"], "active")
        self.assertEqual(state["nodes"][-1]["baseline"]["node"], "measure")

    def test_source_without_reference_carries_low_confidence(self):
        root = node("root")
        root["facts"] = [{"claim":"待验证的假设","source":None,"confidence":"high"}]
        self.call("init", plan([root]), ok=False)
        root["facts"][0]["confidence"] = "low"
        self.call("init", plan([root]))

    def test_interrupted_phase_can_replan_remaining_work_at_its_close(self):
        self.call("init", plan([node("P"), node("A", "P"), node("B", "P")]))
        self.call("apply", self.event("start", "A"))
        self.call("apply", self.event("close", "P", **close_fields("deviation")), ok=False)
        self.call("apply", self.event("close", "A", **close_fields()))
        self.call("apply", self.event("close", "P", **close_fields()), ok=False)
        changes = [{"retire": "B"}, {"add": node("C", "P", deps=["A"])}]
        self.call("apply", self.event("close", "P", **close_fields("deviation"), changes=changes))
        self.assertEqual(self.state()["work"]["B"]["status"], "retired")
        self.call("apply", self.event("start", "C"))
        self.call("apply", self.event("close", "C", **close_fields()))
        self.call("apply", self.event("close", "P", **close_fields()))
        self.assertEqual(self.state()["work"]["P"]["status"], "passed")

    def test_goal_risk_survives_unrelated_work_and_clears_with_evidence(self):
        self.call("init", plan([node("P"), node("A", "P"), node("B", "P")]))
        self.call("apply", self.event("start", "A"))
        self.call("apply", self.event("close", "A", **close_fields(), goal_risk="需要再核对一份样本。"))
        self.call("apply", self.event("start", "B"))
        self.assertEqual(self.state()["risk"], "需要再核对一份样本。")
        self.call("apply", self.event("close", "B", **close_fields()))
        self.assertEqual(self.state()["risk"], "需要再核对一份样本。")
        self.call("apply", self.event("close", "P", **close_fields(), goal_risk=""))
        self.assertEqual(self.state()["risk"], "")
        self.assertEqual(self.state()["history"][2]["result"]["goal_risk"], "需要再核对一份样本。")

    def test_publish_failure_leaves_previous_report_readable(self):
        self.call("init", plan([node("P")]))
        original = self.html.read_bytes()
        snippet = """import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
import plan
path = Path(sys.argv[2])
with patch.object(plan.os, 'replace', side_effect=OSError('write interrupted')):
    try:
        plan.publish(path, plan.read_report(path))
    except OSError as error:
        assert str(error) == 'write interrupted'
    else:
        raise AssertionError('expected an interrupted publish')
"""
        subprocess.run([sys.executable, "-c", snippet, str(CLI.parent), str(self.html)], check=True)
        self.assertEqual(self.html.read_bytes(), original)
        self.assertEqual(self.state()["revision"], 1)
        self.assertFalse(list(self.folder.glob("*.tmp")))

    def test_missing_external_input_is_visible_and_requires_observed_receipt(self):
        intake = node("intake", "P")
        intake["awaiting_input"] = "等待财务提供当天的真实明细。"
        self.call("init", plan([node("P"), intake, node("use", "P", deps=["intake"])]))
        def status():
            raw = subprocess.check_output([sys.executable, str(CLI), "status", str(self.html)], text=True)
            return json.loads(raw)
        self.assertEqual(status()["ready"], [])
        self.assertEqual(status()["awaiting_input"], {"intake": intake["awaiting_input"]})
        event = self.event("start", "intake")
        self.call("apply", event, ok=False)
        self.call("apply", dict(event, input_evidence="已只读打开实际明细.csv，确认表头和五行数据。"))
        self.assertEqual(status()["awaiting_input"], {})
        self.assertIn("五行", self.state()["history"][-1]["input_evidence"])
        self.call("apply", self.event("close", "intake", **close_fields()))
        self.assertEqual(status()["ready"], ["use"])

    def test_missing_measurement_and_interrupted_attempt_do_not_unlock_results(self):
        follow = node("use", "P", deps=[{"id": "measure", "needs": "evidence"}])
        self.call("init", plan([node("P"), node("measure", "P"), follow]))
        self.call("apply", self.event("start", "measure"))
        for verdict in ("interrupted", "deviation"):
            self.call("apply", self.event("close", "measure", **close_fields(verdict),
                                         duration_seconds=None, time_source="进程退出，结束时间未记录。"))
            self.call("apply", self.event("start", "use"), ok=False)
            self.call("apply", self.event("start", "measure"))
        self.call("apply", self.event("close", "measure", **close_fields("deviation"),
                                     usable_evidence="输出中两条错例可供后续核对，见测量记录。"))
        self.call("apply", self.event("start", "use"))

    def test_active_forecasts_keep_their_original_basis_and_agreed_criteria(self):
        self.call("init", plan([node("P"), node("measure", "P"), node("work", "P")]))
        self.call("apply", self.event("start", "measure"))
        change = {"edit": "P", "set": {"expected": "按真实样本重估", "estimate_minutes": [5, 20],
                                       "rationale": "根据本轮实测扩大区间。"}}
        self.call("apply", self.event("close", "measure", **close_fields(), changes=[change]))
        self.assertEqual(self.state()["nodes"][0]["expected"], "按真实样本重估")
        self.call("apply", self.event("start", "work"))
        self.call("apply", self.event("close", "work", **close_fields(),
                                     changes=[{"edit": "P", "set": {"acceptance": "降低门槛"}}]), ok=False)
        self.call("apply", self.event("close", "work", **close_fields()))
        self.call("apply", self.event("close", "P", **close_fields()))
        state = self.state()
        self.assertEqual(state["history"][-1]["forecast"]["expected"], "结果与输入一致")
        self.assertEqual(state["nodes"][0]["acceptance"], "重新测量并对照输入")

    def test_measurement_blocks_consumers_while_the_framework_can_run(self):
        measure = node("measure", "P")
        data = {"metric": "准确率", "method": "复测样本", "node": "measure"}
        parent = dict(node("P"), baseline=data)
        consumer = dict(node("use", "P"), baseline=data)
        frame = dict(node("frame", "P"), baseline=dict(data, use="forecast"))
        self.call("init", plan([parent, measure, consumer, frame]))
        self.call("apply", self.event("start", "use"), ok=False)
        self.call("apply", self.event("start", "frame"))
        self.call("apply", self.event("start", "measure"))
        self.call("apply", self.event("close", "measure", **close_fields()))
        self.call("apply", self.event("start", "use"))

    @unittest.skipIf(sys.platform == "win32", "uses a POSIX lock holder")
    def test_held_writer_lock_has_a_bounded_retry(self):
        import fcntl
        self.call("init", plan([node("P")]))
        code = """import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
import plan
with patch.object(plan.time, 'monotonic', side_effect=[10, 22]):
    try:
        with plan.locked(Path(sys.argv[2])):
            raise AssertionError('second writer acquired lock')
    except plan.Conflict:
        pass
"""
        with (self.folder / ("." + self.html.name + ".lock")).open("a+b") as holder:
            fcntl.flock(holder.fileno(), fcntl.LOCK_EX)
            subprocess.run([sys.executable, "-c", code, str(CLI.parent), str(self.html)], check=True, timeout=2.5)


if __name__ == "__main__":
    unittest.main()
