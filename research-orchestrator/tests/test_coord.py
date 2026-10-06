"""Boundary tests against the real CLI, using only temporary local files."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "coord.py"
TIME1 = "2026-10-04T12:00:00+08:00"
TIME2 = "2026-10-04T12:01:00+08:00"


class CoordTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def save(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def run_cli(self, *args, ok=True):
        process = subprocess.run([sys.executable, str(SCRIPT)] + [str(arg) for arg in args],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 encoding="utf-8", cwd=str(self.root))
        self.assertEqual(process.stderr, "", process.stderr)
        output = json.loads(process.stdout)
        self.assertEqual(process.returncode, 0 if ok else 2, output)
        self.assertIs(output["ok"], ok, output)
        return output

    def task(self, **changes):
        data = {"schema_version": 1, "task_id": "A1", "task_kind": "research",
                "objective": "检验精确值 58.07→42.57 ps", "read_first": [{"path": "missing-history.md", "purpose": "只列路径"}],
                "allowed_write_roots": ["outputs"], "expected_outputs": [{"path": "outputs/a.dat", "description": "原始结果"}],
                "done_criteria": ["保留失败/未知"], "global_constraints": ["CPU <= 19.125 s", "不要执行 $(Get-Process)"],
                "report_path": "report.md", "result_path": "result.json"}
        data.update(changes)
        return data

    def receipt(self, **changes):
        artifact = self.root / "artifact.dat"
        artifact.write_bytes(b"actual evidence\n")
        data = {"schema_version": 1, "task_id": "A1", "work_status": "DONE", "summary": "author finished",
                "artifacts": [{"path": artifact.name, "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}],
                "validation": {"status": "passed", "evidence_refs": ["validation.md"]},
                "concerns": [], "missing_inputs": [], "scientific_identity_changed": False,
                "review": {"status": "accepted", "report_ref": "review.md", "accepted_scope": ["claimed scope"]},
                "costs": {"cpu_s": 1.0, "native_wall_s": 2.0, "model_cost": None}}
        data.update(changes)
        return data

    def state(self, tasks=None, queue=None, **changes):
        data = {"schema_version": 1, "objective": "验证模型", "objective_complete": False,
                "author_defaults": {"model": "gpt-6.1-sol", "effort": "xhigh"},
                "tasks": tasks or [], "support_queue": queue or []}
        data.update(changes)
        return data

    def state_task(self, task_id="A1", **changes):
        data = {"task_id": task_id, "role": "author", "status": "RUNNING", "brief_path": None,
                "result_path": None, "blocker": None}
        data.update(changes)
        return data

    def support(self, support_id="S1", **changes):
        data = {"support_id": support_id, "status": "queued", "family": "inventory",
                "read_first": [{"path": "inputs.json", "purpose": "本地清单"}],
                "allowed_write_roots": ["support"], "expected_outputs": [{"path": support_id + ".json", "description": "清单"}],
                "owner_role": "author", "scientific_identity_changed": False, "mutates_independent_report": False}
        data.update(changes)
        return data

    def test_brief_defaults_constraints_and_no_link_reads(self):
        task = self.task()
        path = self.save("task.json", task)
        destination = self.root / "brief.md"
        output = self.run_cli("brief", "--task", path, "--output", destination)
        self.assertEqual(output["configuration"], {"model": "gpt-6.1-sol", "effort": "xhigh"})
        self.assertFalse(output["linked_content_read"])
        self.assertNotIn("职责、接收与升级", output["brief_markdown"])
        self.assertEqual(destination.read_text(encoding="utf-8"), output["brief_markdown"])
        for exact in task["global_constraints"] + [task["objective"], "missing-history.md"]:
            self.assertIn(exact, output["brief_markdown"])

    def test_brief_preserves_responsibility_routes_decisions_and_commands_as_data(self):
        marker = self.root / "command-must-not-execute.txt"
        command = "$(Set-Content -LiteralPath '" + str(marker) + "' -Value 'executed')"
        responsibility = {"execution_owner": "作者 A", "delivery_receiver": "集成作者 B",
                          "acceptance_owner": "主控 C", "review_owner": None, "escalate_to": "主控 C",
                          "routine_decisions": ["在原合同内决定目录核对顺序", command],
                          "escalate_when": ["科学身份改变", "累计硬预算余额不足"],
                          "future_routing_field": {"command_text": command, "assignment_evidence": None}}
        source = self.save("task.json", self.task(responsibility=responsibility))
        original = source.read_bytes()
        destination = self.root / "brief.md"
        output = self.run_cli("brief", "--task", source, "--output", destination)
        section = output["brief_markdown"].split("## 职责、接收与升级\n\n```json\n", 1)[1].split("```\n", 1)[0]
        self.assertEqual(json.loads(section), responsibility)
        self.assertEqual(destination.read_text(encoding="utf-8"), output["brief_markdown"])
        self.assertEqual(output["configuration"], {"model": "gpt-6.1-sol", "effort": "xhigh"})
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(marker.exists())

    def test_responsibility_accepts_unassigned_and_omitted_fields(self):
        unassigned = {"execution_owner": None, "delivery_receiver": None, "acceptance_owner": None,
                      "review_owner": None, "escalate_to": None, "routine_decisions": [], "escalate_when": []}
        for responsibility in ({}, unassigned, {"routine_decisions": [""]}):
            with self.subTest(responsibility=responsibility):
                output = self.run_cli("brief", "--task", self.save("task.json", self.task(responsibility=responsibility)))
                section = output["brief_markdown"].split("## 职责、接收与升级\n\n```json\n", 1)[1].split("```\n", 1)[0]
                self.assertEqual(json.loads(section), responsibility)
                self.assertNotIn("dispatch_id", output)

    def test_responsibility_bad_types_fail_without_generating_brief(self):
        invalid = [None, [], "routing", {"execution_owner": "  "}]
        invalid.extend({field: []} for field in ("execution_owner", "delivery_receiver", "acceptance_owner", "review_owner", "escalate_to"))
        for field in ("routine_decisions", "escalate_when"):
            invalid.extend(({field: "not-an-array"}, {field: [None]}))
        destination = self.root / "brief.md"
        for responsibility in invalid:
            with self.subTest(responsibility=responsibility):
                output = self.run_cli("brief", "--task", self.save("task.json", self.task(responsibility=responsibility)),
                                      "--output", destination, ok=False)
                self.assertIn("task.responsibility", " ".join(output["errors"]))
                self.assertFalse(destination.exists())

    def test_brief_reviewer_unknown_and_explicit_models_preserved(self):
        for kind in ("review", "integration"):
            output = self.run_cli("brief", "--task", self.save("task.json", self.task(task_kind=kind)))
            self.assertEqual(output["configuration"], {"model": None, "effort": None})
        output = self.run_cli("brief", "--task", self.save("task.json", self.task(model="selected-model", effort="high")))
        self.assertEqual(output["configuration"], {"model": "selected-model", "effort": "high"})

    def test_brief_empty_identity_is_error(self):
        for field in ("task_id", "objective"):
            for value in (None, "", "  "):
                self.run_cli("brief", "--task", self.save("task.json", self.task(**{field: value})), ok=False)

    def test_done_and_report_claims_are_not_science_acceptance(self):
        receipt = self.receipt()
        receipt["review"]["report_ref"] = "$(Get-Process); review.md"
        output = self.run_cli("check-result", "--result", self.save("result.json", receipt))
        self.assertEqual(output["artifact_identity"]["status"], "matched")
        self.assertEqual(output["work_status"], "DONE")
        self.assertEqual(output["validation_record"]["status"], "passed")
        self.assertEqual(output["science_acceptance"], "not_decided")
        self.assertEqual(output["task_contract"]["status"], "not_checked")
        self.assertFalse((self.root / "review.md").exists())

    def test_contract_requires_report_and_outputs_even_when_existing_hashes_match(self):
        task = self.task(expected_outputs=[{"path": "artifact.dat", "description": "原始结果"}], report_path="report.md")
        contract = self.save("task.json", task)
        for status in ("DONE", "DONE_WITH_CONCERNS"):
            receipt = self.receipt(work_status=status)
            output = self.run_cli("check-result", "--result", self.save("result.json", receipt), "--task", contract, ok=False)
            self.assertEqual(output["artifact_identity"]["status"], "matched")
            self.assertEqual(output["task_contract"]["status"], "failed")
            self.assertTrue(output["task_contract"]["required_deliveries"][0]["identity_matched"])
            self.assertFalse(output["task_contract"]["required_deliveries"][1]["artifact_listed"])
        report = self.root / "report.md"
        report.write_bytes(b"reported observations\n")
        receipt = self.receipt()
        self.run_cli("check-result", "--result", self.save("result.json", receipt), "--task", contract, ok=False)
        receipt["artifacts"].append({"path": "report.md", "sha256": hashlib.sha256(report.read_bytes()).hexdigest()})
        output = self.run_cli("check-result", "--result", self.save("result.json", receipt), "--task", contract)
        self.assertEqual(output["task_contract"]["status"], "matched")
        self.assertFalse(output["task_contract"]["done_criteria_checked"])
        self.assertEqual(output["science_acceptance"], "not_decided")
        task["task_id"] = "other-task"
        output = self.run_cli("check-result", "--result", self.save("result.json", receipt), "--task", self.save("task.json", task), ok=False)
        self.assertFalse(output["task_contract"]["task_id_matched"])
        self.assertEqual(output["artifact_identity"]["status"], "matched")
        task["task_id"] = receipt["task_id"]
        task["expected_outputs"].append({"path": "missing-output.dat", "description": "另一个必交产物"})
        output = self.run_cli("check-result", "--result", self.save("result.json", receipt), "--task", self.save("task.json", task), ok=False)
        self.assertIn("missing-output.dat", " ".join(output["errors"]))

    def test_contract_resolves_root_and_absolute_paths_and_blocked_identity(self):
        contracts = self.root / "contracts"
        contracts.mkdir()
        receipt = self.receipt()
        task = self.task(expected_outputs=[{"path": str(self.root / "artifact.dat"), "description": "绝对路径交付"}], report_path=None)
        result = self.save("contracts/result.json", receipt)
        contract = self.save("contracts/task.json", task)
        output = self.run_cli("check-result", "--result", result, "--task", contract, "--root", self.root)
        self.assertEqual(output["task_contract"]["status"], "matched")
        task["expected_outputs"][0]["path"] = "artifact.dat"
        output = self.run_cli("check-result", "--result", result, "--task", self.save("contracts/task.json", task), "--root", self.root)
        self.assertEqual(output["task_contract"]["status"], "matched")
        blocked = self.receipt(work_status="BLOCKED", artifacts=[])
        task["expected_outputs"][0]["path"] = "not-produced.dat"
        output = self.run_cli("check-result", "--result", self.save("result.json", blocked), "--task", self.save("task.json", task))
        self.assertFalse(output["task_contract"]["delivery_checked"])
        self.assertTrue(output["task_contract"]["task_id_matched"])
        self.assertEqual(output["science_acceptance"], "not_decided")

    def test_missing_and_wrong_hash_are_errors(self):
        receipt = self.receipt()
        receipt["artifacts"][0]["path"] = "missing.dat"
        output = self.run_cli("check-result", "--result", self.save("result.json", receipt), ok=False)
        self.assertIn("missing", " ".join(output["errors"]))
        receipt = self.receipt()
        receipt["artifacts"][0]["sha256"] = "0" * 64
        output = self.run_cli("check-result", "--result", self.save("result.json", receipt), ok=False)
        self.assertIn("SHA256 mismatch", " ".join(output["errors"]))
        self.assertEqual(output["science_acceptance"], "not_decided")

    def test_traversal_and_absolute_escape_rejected(self):
        subroot = self.root / "allowed"
        subroot.mkdir()
        for path in ("../artifact.dat", str(self.root / "artifact.dat")):
            receipt = self.receipt()
            receipt["artifacts"][0]["path"] = path
            output = self.run_cli("check-result", "--result", self.save("result.json", receipt), "--root", subroot, ok=False)
            self.assertIn("outside root", " ".join(output["errors"]))

    def test_symlink_escape_when_supported(self):
        allowed = self.root / "allowed"
        allowed.mkdir()
        outside = self.root / "outside.dat"
        outside.write_bytes(b"secret")
        link = allowed / "link.dat"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("OS account cannot create symlinks")
        receipt = self.receipt(artifacts=[{"path": "link.dat", "sha256": hashlib.sha256(b"secret").hexdigest()}])
        self.run_cli("check-result", "--result", self.save("result.json", receipt), "--root", allowed, ok=False)

    def test_empty_artifacts_only_done_requires_actual_output(self):
        self.run_cli("check-result", "--result", self.save("result.json", self.receipt(artifacts=[])), ok=False)
        for status in ("BLOCKED", "NEEDS_CONTEXT"):
            output = self.run_cli("check-result", "--result", self.save("result.json", self.receipt(work_status=status, artifacts=[])))
            self.assertEqual(output["artifact_identity"]["status"], "no_artifacts")
            self.assertEqual(output["science_acceptance"], "not_decided")

    def test_structure_errors_and_arguments_have_json_failure(self):
        receipt = self.receipt()
        receipt["costs"]["cpu_s"] = True
        self.run_cli("check-result", "--result", self.save("result.json", receipt), ok=False)
        for command, option, data in (
                ("brief", "--task", self.task(task_kind=[])),
                ("check-result", "--result", self.receipt(work_status={})),
                ("support-queue", "--state", self.state(queue=[self.support(family=[])]))):
            self.run_cli(command, option, self.save("malformed.json", data), ok=False)
        tasks = [self.state_task("good"), self.state_task("bad", signals={"progress": {"value": True, "basis": []}})]
        output = self.run_cli("snapshot", "--state", self.save("state.json", self.state(tasks)), ok=False)
        self.assertEqual([task["task_id"] for task in output["tasks"]], ["good", "bad"])
        self.run_cli("snapshot", ok=False)
        path = self.root / "broken.json"
        path.write_text("{broken", encoding="utf-8")
        self.run_cli("brief", "--task", path, ok=False)

    def test_silence_and_log_claims_remain_unknown_or_claimed(self):
        log = {"value": True, "source": "worker.log", "observed_at": TIME1, "evidence_refs": ["worker.log"], "basis": "log"}
        weak = copy.deepcopy(log)
        weak["basis"] = "checked_artifact"
        weak["evidence_refs"] = []
        tasks = [self.state_task("silent"), self.state_task("logs", signals={"activity": log, "progress": log}),
                 self.state_task("weak", signals={"progress": weak})]
        output = self.run_cli("snapshot", "--state", self.save("state.json", self.state(tasks)))
        self.assertEqual(output["exceptional"], [])
        self.assertEqual(output["completed_pending_acceptance"], [])
        self.assertEqual(output["tasks"][0]["signals"]["liveness"]["assessment"], "unknown")
        self.assertEqual(output["tasks"][0]["signals"]["progress"]["assessment"], "unknown")
        self.assertEqual(output["tasks"][1]["signals"]["progress"]["assessment"], "claimed")
        self.assertEqual(output["tasks"][2]["signals"]["progress"]["assessment"], "claimed")

    def test_checked_records_and_recorded_objective_only(self):
        signal = {"value": True, "source": "reviewer receipt", "observed_at": TIME1, "evidence_refs": ["A1.dat"], "basis": "accepted_checkpoint"}
        tasks = [self.state_task(role="research", status="DONE", signals={"progress": signal}), self.state_task("A2", status="NEEDS_CONTEXT")]
        output = self.run_cli("snapshot", "--state", self.save("state.json", self.state(tasks, objective_complete=False)))
        self.assertEqual(output["tasks"][0]["signals"]["progress"]["assessment"], "checked_record")
        self.assertEqual(output["completed_pending_acceptance"], ["A1"])
        self.assertEqual(output["pending_review"], ["A1"])
        self.assertEqual(output["needs_context"], ["A2"])
        self.assertEqual(output["objective_complete"], {"recorded": False})

    def test_review_requirement_respects_role_and_explicit_records(self):
        tasks = [self.state_task("support", role="support", status="DONE_WITH_CONCERNS"),
                 self.state_task("research", role="research", status="DONE"),
                 self.state_task("author", role="author", status="DONE"),
                 self.state_task("integration", role="integration", status="DONE"),
                 self.state_task("required", role="support", status="DONE", review_required=True),
                 self.state_task("not-required", role="support", status="DONE", review_required=False),
                 self.state_task("explicit", role="integration", status="PENDING_REVIEW")]
        output = self.run_cli("snapshot", "--state", self.save("state.json", self.state(tasks)))
        self.assertEqual(output["pending_review"], ["research", "required", "explicit"])
        self.assertIn("support", output["completed_pending_acceptance"])
        self.assertIs(output["tasks"][4]["review_required"], True)
        self.assertIs(output["tasks"][5]["review_required"], False)
        self.assertIsNone(output["tasks"][0]["review_required"])
        invalid = self.state([self.state_task("invalid", role="support", status="DONE", review_required="true")])
        output = self.run_cli("snapshot", "--state", self.save("invalid-review.json", invalid), ok=False)
        self.assertEqual(output["pending_review"], [])
        self.assertIn("review_required", " ".join(output["task_issues"][0]["errors"]))

    def test_unsourced_true_and_false_are_claims_not_observations(self):
        tasks = []
        for value in (True, False):
            signal = {"value": value, "source": None, "observed_at": TIME1, "evidence_refs": ["claimed.dat"], "basis": "checked_artifact"}
            tasks.append(self.state_task(str(value), signals={kind: signal for kind in ("liveness", "activity", "progress")}))
        sourced_false = {"value": False, "source": "worker state", "observed_at": TIME1, "evidence_refs": ["state.json"], "basis": "state_record"}
        tasks.append(self.state_task("sourced", signals={kind: sourced_false for kind in ("liveness", "activity", "progress")}))
        output = self.run_cli("snapshot", "--state", self.save("state.json", self.state(tasks)))
        for task, value in zip(output["tasks"][:2], (True, False)):
            for signal in task["signals"].values():
                self.assertIs(signal["value"], value)
                self.assertEqual(signal["assessment"], "claimed")
        self.assertEqual(output["tasks"][2]["signals"]["liveness"]["assessment"], "recorded")
        self.assertEqual(output["tasks"][2]["signals"]["progress"]["assessment"], "recorded_no_progress")
        self.assertEqual(output["exceptional"], [])
        self.assertEqual(output["completed_pending_acceptance"], [])

    def test_delta_ignores_observation_time_but_tracks_evidence(self):
        signal = {"value": True, "source": "local receipt", "observed_at": TIME1, "evidence_refs": ["A1.dat"], "basis": "checked_artifact"}
        state = self.state([self.state_task(signals={"progress": signal})])
        source = self.save("state.json", state)
        previous = self.root / "previous.json"
        self.run_cli("snapshot", "--state", source, "--output", previous)
        signal["observed_at"] = TIME2
        output = self.run_cli("snapshot", "--state", self.save("state.json", state), "--previous", previous)
        self.assertEqual(output["changed_task_ids"], [])
        signal["evidence_refs"] = ["A1-v2.dat"]
        output = self.run_cli("snapshot", "--state", self.save("state.json", state), "--previous", previous)
        self.assertEqual(output["changed_task_ids"], ["A1"])

    def test_observation_time_requires_timezone_and_preserves_other_tasks(self):
        times = ["2026-10-04T04:00:00Z", TIME1, None, "not-a-time", "2026-10-04T12:00:00"]
        tasks = [self.state_task("T" + str(index), signals={"activity": {
            "value": True, "source": "worker.log", "observed_at": time,
            "evidence_refs": ["worker.log"], "basis": "log"}}) for index, time in enumerate(times)]
        output = self.run_cli("snapshot", "--state", self.save("state.json", self.state(tasks)), ok=False)
        self.assertEqual([task["task_id"] for task in output["tasks"]], ["T0", "T1", "T2", "T3", "T4"])
        self.assertEqual([task["record_valid"] for task in output["tasks"]], [True, True, True, False, False])
        self.assertEqual([issue["task_id"] for issue in output["task_issues"]], ["T3", "T4"])
        self.assertIn("timezone", " ".join(output["task_issues"][0]["errors"]))

    def test_malformed_task_retains_readable_tasks_and_is_not_success(self):
        tasks = [self.state_task("good", status="DONE"), "corrupt", self.state_task("bad", signals={"progress": {"value": "true"}})]
        destination = self.root / "partial.json"
        output = self.run_cli("snapshot", "--state", self.save("state.json", self.state(tasks)), "--output", destination, ok=False)
        self.assertEqual([task["task_id"] for task in output["tasks"]], ["good", "bad"])
        self.assertEqual(len(output["task_issues"]), 2)
        self.assertIn("good", output["completed_pending_acceptance"])
        self.assertFalse(json.loads(destination.read_text(encoding="utf-8"))["ok"])

    def test_support_queue_grouping_limit_and_assigned_skip(self):
        queue = [self.support("S1"), self.support("S2"), self.support("S3"), self.support("assigned", status="assigned")]
        output = self.run_cli("support-queue", "--state", self.save("state.json", self.state(queue=queue)), "--max-items", 2)
        self.assertTrue(output["proposals_only"])
        self.assertEqual(output["proposals"][0]["support_ids"], ["S1", "S2"])
        self.assertEqual(output["proposals"][0]["model"], "gpt-6.1-sol")
        self.assertEqual(output["proposals"][0]["effort"], "xhigh")
        self.assertEqual(output["assigned_skipped"], ["assigned"])
        self.assertEqual(output["remaining_count"], 1)
        self.assertNotIn("dispatch_id", json.dumps(output))

    def test_bad_support_entries_retain_only_valid_suggestions(self):
        queue = [self.support("same", family=[]), self.support("same"), "corrupt", self.support("assigned", status="assigned")]
        state = self.save("state.json", self.state(queue=queue))
        original = state.read_bytes()
        destination = self.root / "partial-queue.json"
        output = self.run_cli("support-queue", "--state", state, "--output", destination, ok=False)
        self.assertEqual(output["proposals"][0]["support_ids"], ["same"])
        self.assertEqual(output["eligible_count"], 1)
        self.assertEqual(output["assigned_skipped"], ["assigned"])
        self.assertEqual([item["index"] for item in output["queue_issues"]], [0, 2])
        self.assertFalse(json.loads(destination.read_text(encoding="utf-8"))["ok"])
        self.assertEqual(state.read_bytes(), original)

    def test_assigned_output_conflict_blocks_only_overlapping_proposal(self):
        queue = [self.support("Q1", expected_outputs=[{"path": "support/Q1.json", "description": "同一输出"}]),
                 self.support("Q2"), self.support("Q3", status="assigned", expected_outputs=[{
                     "path": "support/./Q1.json", "description": "已分配输出"}])]
        output = self.run_cli("support-queue", "--state", self.save("state.json", self.state(queue=queue)))
        self.assertEqual(output["proposals"][0]["support_ids"], ["Q2"])
        self.assertEqual(output["assigned_skipped"], ["Q3"])
        self.assertEqual(output["manual_review"][0]["support_id"], "Q1")
        self.assertEqual(output["manual_review"][0]["reasons"], ["output_conflict_with_assigned"])
        conflict = output["manual_review"][0]["conflicts"][0]
        self.assertEqual(conflict["support_id"], "Q3")
        self.assertEqual(conflict["path"], "support/Q1.json")

    def test_queued_cross_batch_output_conflicts_require_manual_handling(self):
        shared = [{"path": "shared.json", "description": "同一输出"}]
        queue = [self.support("Q1", expected_outputs=shared), self.support("Q2", family="metadata", expected_outputs=shared), self.support("Q3")]
        output = self.run_cli("support-queue", "--state", self.save("state.json", self.state(queue=queue)))
        self.assertEqual(output["proposals"][0]["support_ids"], ["Q3"])
        self.assertEqual([item["support_id"] for item in output["manual_review"]], ["Q1", "Q2"])
        self.assertEqual(output["manual_review"][0]["conflicts"][0]["support_id"], "Q2")
        self.assertEqual(output["manual_review"][1]["conflicts"][0]["support_id"], "Q1")

    def test_support_review_unknown_science_and_research_excluded(self):
        queue = [self.support("ordinary"), self.support("report", mutates_independent_report=True),
                 self.support("science", scientific_identity_changed=True), self.support("unknown", scientific_identity_changed=None),
                 self.support("ownership", mutates_independent_report=None), self.support("reviewer", owner_role="reviewer"),
                 self.support("research", task_kind="research")]
        output = self.run_cli("support-queue", "--state", self.save("state.json", self.state(queue=queue)))
        self.assertEqual(output["proposals"][0]["support_ids"], ["ordinary"])
        self.assertEqual({entry["support_id"] for entry in output["manual_review"]}, {"report", "science", "unknown", "ownership", "reviewer"})
        reviewer = next(item for item in output["manual_review"] if item["support_id"] == "reviewer")
        self.assertIsNone(reviewer["model"])
        self.assertEqual(output["excluded"][0]["support_id"], "research")

    def test_support_configuration_and_write_roots_are_group_boundaries(self):
        queue = [self.support("default"), self.support("explicit", model="custom", effort="high"),
                 self.support("root", allowed_write_roots=["other"]), self.support("family", family="log_summary")]
        output = self.run_cli("support-queue", "--state", self.save("state.json", self.state(queue=queue, author_defaults={"model": "chosen", "effort": "max"})))
        self.assertEqual(len(output["proposals"]), 4)
        self.assertEqual(output["proposals"][0]["model"], "chosen")
        self.assertEqual(output["proposals"][0]["effort"], "max")
        self.assertEqual(output["proposals"][1]["model"], "custom")
        self.assertEqual(output["proposals"][1]["effort"], "high")

    def test_outputs_never_overwrite_inputs(self):
        source = self.save("task.json", self.task())
        initial = source.read_bytes()
        self.run_cli("brief", "--task", source, "--output", source, ok=False)
        self.assertEqual(source.read_bytes(), initial)
        state = self.save("state.json", self.state())
        for command in ("snapshot", "support-queue"):
            original = state.read_bytes()
            self.run_cli(command, "--state", state, "--output", state, ok=False)
            self.assertEqual(state.read_bytes(), original)
        result = self.save("result.json", self.receipt())
        artifact = self.root / "artifact.dat"
        original = artifact.read_bytes()
        self.run_cli("check-result", "--result", result, "--output", artifact, ok=False)
        self.assertEqual(artifact.read_bytes(), original)
        original = source.read_bytes()
        output = self.run_cli("check-result", "--result", result, "--task", source, "--output", source, ok=False)
        self.assertIn("overwrite input", " ".join(output["errors"]))
        self.assertEqual(source.read_bytes(), original)
        previous = self.root / "previous.json"
        self.run_cli("snapshot", "--state", state, "--output", previous)
        original = previous.read_bytes()
        self.run_cli("snapshot", "--state", state, "--previous", previous, "--output", previous, ok=False)
        self.assertEqual(previous.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
