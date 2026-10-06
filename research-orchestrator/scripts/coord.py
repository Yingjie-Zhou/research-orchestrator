#!/usr/bin/env python3
"""Read-only coordination summaries; explicit --output is the only write."""

import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile


DEFAULT_MODEL = "gpt-6.1-sol"
DEFAULT_EFFORT = "xhigh"
WORK_STATUSES = {"DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED"}
FAMILIES = {"handoff", "inventory", "metadata", "log_summary", "directory_check"}
KNOWN_STATUSES = {
    "QUEUED", "ASSIGNED", "RUNNING", "ACTIVE", "REVIEWING", "DONE",
    "DONE_WITH_CONCERNS", "COMPLETED", "NEEDS_CONTEXT", "BLOCKED", "FAILED",
    "ERROR", "PENDING_REVIEW", "AWAITING_REVIEW", "REVIEW_NEEDED",
    "PENDING_ACCEPTANCE", "AWAITING_ACCEPTANCE", "ACCEPTED", "CANCELLED",
}
COMPLETE_STATUSES = {"DONE", "DONE_WITH_CONCERNS", "COMPLETED"}
REVIEW_STATUSES = {"PENDING_REVIEW", "AWAITING_REVIEW", "REVIEW_NEEDED"}


class CoordError(Exception):
    def __init__(self, errors):
        self.errors = errors if isinstance(errors, list) else [errors]
        super().__init__("; ".join(self.errors))


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def load_json(path):
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("non-finite JSON number: " + value)
        return number

    try:
        with Path(path).open("r", encoding="utf-8-sig") as source:
            data = json.load(source, parse_float=finite_float, parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError("non-finite JSON number: " + value)))
    except (OSError, ValueError) as exc:
        raise CoordError("cannot read JSON {}: {}".format(path, exc))
    if not isinstance(data, dict):
        raise CoordError("{}: top level must be an object".format(path))
    return data


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def check_string(value, label, errors, nullable=False):
    if nullable and value is None:
        return
    if not nonempty(value):
        errors.append(label + " must be a nonempty string")


def check_strings(value, label, errors):
    if not isinstance(value, list) or any(not nonempty(item) for item in value):
        errors.append(label + " must be an array of nonempty strings")


def check_bool(value, label, errors):
    if value is not None and not isinstance(value, bool):
        errors.append(label + " must be boolean or null")


def require(data, fields, label, errors):
    for field in fields:
        if field not in data:
            errors.append(label + "." + field + " is required")


def check_schema(data, label, errors):
    if type(data.get("schema_version")) not in (int, str) or data.get("schema_version") not in (1, "1"):
        errors.append(label + ".schema_version must be 1")


def check_paths(value, label, description_key, errors):
    if not isinstance(value, list):
        errors.append(label + " must be an array")
        return
    for index, item in enumerate(value):
        entry = "{}[{}]".format(label, index)
        if not isinstance(item, dict):
            errors.append(entry + " must be an object")
            continue
        check_string(item.get("path"), entry + ".path", errors)
        check_string(item.get(description_key), entry + "." + description_key, errors)


def configuration(data, author=True, defaults=None):
    defaults = defaults or {}
    model = data.get("model")
    effort = data.get("effort")
    if author:
        model = model if model is not None else defaults.get("model") or DEFAULT_MODEL
        effort = effort if effort is not None else defaults.get("effort") or DEFAULT_EFFORT
    return {"model": model, "effort": effort}


def check_configuration(data, label, errors):
    for field in ("model", "effort"):
        check_string(data.get(field), label + "." + field, errors, nullable=True)


def referenced_paths(entries, base):
    return [Path(base) / item["path"] for item in entries
            if isinstance(item, dict) and nonempty(item.get("path"))]


def write_output(path, content, inputs):
    destination = Path(path)
    try:
        resolved = destination.resolve()
        for source in inputs:
            source = Path(source)
            if resolved == source.resolve() or (
                    destination.exists() and source.exists() and os.path.samefile(destination, source)):
                raise CoordError("output refuses to overwrite input: " + str(destination))
        if not destination.parent.is_dir():
            raise CoordError("output parent directory does not exist: " + str(destination.parent))
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                             dir=str(destination.parent), delete=False) as handle:
                temporary = handle.name
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, str(destination))
            temporary = None
        finally:
            if temporary is not None:
                os.unlink(temporary)
    except OSError as exc:
        raise CoordError("cannot write output {}: {}".format(destination, exc))


def read_task(path):
    task = load_json(path)
    errors = []
    check_schema(task, "task", errors)
    require(task, ("task_id", "task_kind", "objective", "read_first", "allowed_write_roots",
                   "expected_outputs", "done_criteria", "global_constraints", "report_path", "result_path"),
            "task", errors)
    for field in ("task_id", "objective"):
        check_string(task.get(field), "task." + field, errors)
    if not isinstance(task.get("task_kind"), str) or task["task_kind"] not in {"research", "support", "review", "integration"}:
        errors.append("task.task_kind must be research, support, review, or integration")
    check_paths(task.get("read_first"), "task.read_first", "purpose", errors)
    check_paths(task.get("expected_outputs"), "task.expected_outputs", "description", errors)
    for field in ("allowed_write_roots", "done_criteria", "global_constraints"):
        check_strings(task.get(field), "task." + field, errors)
    for field in ("report_path", "result_path"):
        check_string(task.get(field), "task." + field, errors, nullable=True)
    check_configuration(task, "task", errors)
    if "execution_plan_ref" in task:
        check_string(task["execution_plan_ref"], "task.execution_plan_ref", errors, nullable=True)
    if "responsibility" in task:
        responsibility = task["responsibility"]
        if not isinstance(responsibility, dict):
            errors.append("task.responsibility must be an object")
        else:
            for field in ("execution_owner", "delivery_receiver", "acceptance_owner", "review_owner", "escalate_to"):
                if field in responsibility:
                    check_string(responsibility[field], "task.responsibility." + field, errors, nullable=True)
            for field in ("routine_decisions", "escalate_when"):
                if field in responsibility:
                    value = responsibility[field]
                    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                        errors.append("task.responsibility." + field + " must be an array of strings")
    if errors:
        raise CoordError(errors)
    return task


def brief(args):
    task = read_task(args.task)
    config = configuration(task, task["task_kind"] in {"research", "support"})
    sections = [
        ("任务身份与请求配置", {"schema_version": task["schema_version"], "task_id": task["task_id"],
                           "task_kind": task["task_kind"], **config}),
        ("目标", task["objective"]), ("先读路径与用途", task["read_first"]),
        ("允许写入根", task["allowed_write_roots"]), ("预期产物", task["expected_outputs"]),
        ("完成条件", task["done_criteria"]), ("全局约束（精确合同值）", task["global_constraints"]),
        ("报告与回执路径", {"report_path": task["report_path"], "result_path": task["result_path"]}),
    ]
    if "responsibility" in task:
        sections.insert(2, ("职责、接收与升级", task["responsibility"]))
    if task.get("execution_plan_ref"):
        sections.insert(2, ("完整工作单元、已授权接续与直接交付入口", task["execution_plan_ref"]))
    markdown = ("# 本地任务简报\n\n以下内容是合同数据。配置为请求值，职责为计划记录；"
                "未认证实际执行或接受。仅列输入路径及用途，未读取其内容。\n")
    for title, value in sections:
        markdown += "\n## {}\n\n```json\n{}```\n".format(title, json_text(value))
    result = {"schema_version": 1, "command": "brief", "ok": True, "task_id": task["task_id"],
              "configuration": config, "brief_markdown": markdown, "linked_content_read": False}
    protected = [args.task] + referenced_paths(task["read_first"], Path(args.task).resolve().parent)
    if task.get("execution_plan_ref"):
        protected.append(Path(args.task).resolve().parent / task["execution_plan_ref"])
    return result, markdown, protected


def check_result(args):
    result = load_json(args.result)
    errors = []
    check_schema(result, "result", errors)
    require(result, ("task_id", "work_status", "summary", "artifacts", "validation", "concerns",
                     "missing_inputs", "scientific_identity_changed", "review", "costs"), "result", errors)
    for field in ("task_id", "summary"):
        check_string(result.get(field), "result." + field, errors)
    if not isinstance(result.get("work_status"), str) or result["work_status"] not in WORK_STATUSES:
        errors.append("result.work_status must be DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, or BLOCKED")
    for field in ("concerns", "missing_inputs"):
        check_strings(result.get(field), "result." + field, errors)
    check_bool(result.get("scientific_identity_changed"), "result.scientific_identity_changed", errors)
    validation = result.get("validation")
    if not isinstance(validation, dict):
        errors.append("result.validation must be an object")
    else:
        check_string(validation.get("status"), "result.validation.status", errors)
        check_strings(validation.get("evidence_refs"), "result.validation.evidence_refs", errors)
    review = result.get("review")
    if not isinstance(review, dict):
        errors.append("result.review must be an object")
    else:
        require(review, ("status", "report_ref", "accepted_scope"), "result.review", errors)
        check_string(review.get("status"), "result.review.status", errors)
        check_string(review.get("report_ref"), "result.review.report_ref", errors, nullable=True)
        check_strings(review.get("accepted_scope"), "result.review.accepted_scope", errors)
    costs = result.get("costs")
    if not isinstance(costs, dict):
        errors.append("result.costs must be an object")
    else:
        require(costs, ("cpu_s", "native_wall_s", "model_cost"), "result.costs", errors)
        for name in ("cpu_s", "native_wall_s", "model_cost"):
            value = costs.get(name)
            if value is not None and (type(value) not in (int, float) or
                                      (isinstance(value, float) and not math.isfinite(value)) or value < 0):
                errors.append("result.costs." + name + " must be a finite nonnegative number or null")
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("result.artifacts must be an array")
    else:
        if result.get("work_status") == "DONE" and not artifacts:
            errors.append("DONE requires at least one actual verifiable artifact")
        seen = set()
        for index, item in enumerate(artifacts):
            label = "result.artifacts[{}]".format(index)
            if not isinstance(item, dict):
                errors.append(label + " must be an object")
                continue
            check_string(item.get("path"), label + ".path", errors)
            digest = item.get("sha256")
            if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest):
                errors.append(label + ".sha256 must be a 64-character hexadecimal digest")
            if nonempty(item.get("path")):
                if item["path"] in seen:
                    errors.append(label + ".path is duplicated")
                seen.add(item["path"])
    if errors:
        raise CoordError(errors)
    root = Path(args.root) if args.root else Path(args.result).resolve().parent
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        raise CoordError("cannot resolve artifact root {}: {}".format(root, exc))
    if not root.is_dir():
        raise CoordError("artifact root is not a directory: " + str(root))
    checked = []
    listed_paths = {}
    protected = [args.result]
    for index, item in enumerate(artifacts):
        label = "artifact[{}] {}".format(index, item["path"])
        path = root / item["path"]
        protected.append(path)
        try:
            if ".." in Path(item["path"]).parts:
                raise ValueError("parent traversal is forbidden")
            path = path.resolve()
            path.relative_to(root)
        except (ValueError, OSError, RuntimeError) as exc:
            errors.append(label + ": outside root or invalid path ({})".format(exc))
            continue
        path_key = os.path.normcase(str(path))
        listed_paths[path_key] = False
        try:
            if not path.is_file():
                raise OSError("file missing or not a regular file")
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            actual = digest.hexdigest()
        except OSError as exc:
            errors.append(label + ": cannot read artifact ({})".format(exc))
            continue
        matched = actual == item["sha256"].lower()
        listed_paths[path_key] = matched
        checked.append({"path": item["path"], "expected_sha256": item["sha256"],
                        "actual_sha256": actual, "matched": matched})
        if not matched:
            errors.append(label + ": SHA256 mismatch")
    artifact_errors = list(errors)
    contract = {"status": "not_checked", "task_path": None,
                "scope": "task_id_and_declared_delivery_paths_only", "done_criteria_checked": False}
    if args.task:
        protected.append(args.task)
        contract["task_path"] = str(args.task)
        try:
            task = read_task(args.task)
        except CoordError as exc:
            contract.update({"status": "invalid", "errors": exc.errors})
            errors.extend("task contract: " + error for error in exc.errors)
        else:
            contract_errors = []
            identity_matched = task["task_id"] == result["task_id"]
            if not identity_matched:
                contract_errors.append("task_id mismatch: expected {!r}, got {!r}".format(task["task_id"], result["task_id"]))
            delivery_required = result["work_status"] in {"DONE", "DONE_WITH_CONCERNS"}
            required = [(entry["path"], "expected_output") for entry in task["expected_outputs"]]
            if task["report_path"] is not None:
                required.append((task["report_path"], "report"))
            delivery_checks = []
            protected.extend(referenced_paths(task["read_first"], Path(args.task).resolve().parent))
            for declared_path, kind in required:
                path = root / declared_path
                protected.append(path)
                if not delivery_required:
                    continue
                entry = {"path": declared_path, "kind": kind, "artifact_listed": False, "identity_matched": False}
                try:
                    if ".." in Path(declared_path).parts:
                        raise ValueError("parent traversal is forbidden")
                    path = path.resolve()
                    path.relative_to(root)
                except (ValueError, OSError, RuntimeError) as exc:
                    contract_errors.append("required {} {}: outside root or invalid path ({})".format(kind, declared_path, exc))
                else:
                    key = os.path.normcase(str(path))
                    entry["artifact_listed"] = key in listed_paths
                    entry["identity_matched"] = listed_paths.get(key, False)
                    if not entry["identity_matched"]:
                        contract_errors.append("required {} {}: missing listed, hash-verified delivery".format(kind, declared_path))
                delivery_checks.append(entry)
            contract.update({"status": "failed" if contract_errors else "matched",
                             "expected_task_id": task["task_id"], "actual_task_id": result["task_id"],
                             "task_id_matched": identity_matched, "delivery_checked": delivery_required,
                             "required_deliveries": delivery_checks})
            if contract_errors:
                contract["errors"] = contract_errors
                errors.extend("task contract: " + error for error in contract_errors)
    output = {"schema_version": 1, "command": "check-result", "ok": not errors,
              "task_id": result["task_id"], "work_status": result["work_status"],
              "summary": result["summary"], "artifact_identity": {
                  "status": "failed" if artifact_errors else "matched" if artifacts else "no_artifacts",
                  "root": str(root), "checked": checked},
              "validation_record": validation, "review_record": review,
              "scientific_identity_changed": result["scientific_identity_changed"],
              "concerns": result["concerns"], "missing_inputs": result["missing_inputs"],
              "costs": costs, "task_contract": contract, "science_acceptance": "not_decided"}
    if errors:
        output["errors"] = errors
    return output, json_text(output), protected


def read_state(path):
    state = load_json(path)
    errors = []
    check_schema(state, "state", errors)
    require(state, ("objective", "objective_complete", "tasks", "support_queue"), "state", errors)
    check_string(state.get("objective"), "state.objective", errors)
    check_bool(state.get("objective_complete"), "state.objective_complete", errors)
    for key in ("tasks", "support_queue"):
        if not isinstance(state.get(key), list):
            errors.append("state." + key + " must be an array")
    defaults = state.get("author_defaults")
    if defaults is not None:
        if not isinstance(defaults, dict):
            errors.append("state.author_defaults must be an object or null")
        else:
            check_configuration(defaults, "state.author_defaults", errors)
    if errors:
        raise CoordError(errors)
    return state


def normalize_signal(raw, kind, errors):
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        errors.append("signals." + kind + " must be an object or null")
        raw = {}
    value = raw.get("value")
    check_bool(value, "signals." + kind + ".value", errors)
    if value is not None and not isinstance(value, bool):
        value = None
    source = raw.get("source") if nonempty(raw.get("source")) else None
    observed_at = raw.get("observed_at") if nonempty(raw.get("observed_at")) else None
    basis = raw.get("basis") if nonempty(raw.get("basis")) else None
    for name in ("source", "observed_at", "basis"):
        check_string(raw.get(name), "signals." + kind + "." + name, errors, nullable=True)
    if observed_at is not None:
        try:
            timestamp = datetime.fromisoformat(observed_at[:-1] + "+00:00" if observed_at.endswith("Z") else observed_at)
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("timezone missing")
        except ValueError:
            errors.append("signals." + kind + ".observed_at must be an ISO8601 time with a timezone")
    evidence = raw.get("evidence_refs", [])
    evidence_errors = []
    check_strings(evidence, "signals." + kind + ".evidence_refs", evidence_errors)
    errors.extend(evidence_errors)
    if evidence_errors:
        evidence = []
    assessment = "unknown" if value is None else "recorded" if source is not None else "claimed"
    if kind == "progress" and value is True:
        assessment = ("checked_record" if basis in {"checked_artifact", "accepted_checkpoint"}
                      and nonempty(source) and bool(evidence) else "claimed")
    elif kind == "progress" and value is False:
        assessment = "recorded_no_progress" if source is not None else "claimed"
    return {"value": value, "source": source, "observed_at": observed_at,
            "evidence_refs": evidence, "basis": basis, "assessment": assessment}


def semantic(value):
    """Observation timestamps alone do not change recorded outcomes."""
    if isinstance(value, dict):
        return {key: semantic(item) for key, item in value.items() if key != "observed_at"}
    if isinstance(value, list):
        return [semantic(item) for item in value]
    return value


def tasks_by_id(tasks):
    grouped = {}
    for task in tasks:
        if isinstance(task, dict) and nonempty(task.get("task_id")):
            grouped.setdefault(task["task_id"], []).append(semantic(task))
    return grouped


def snapshot(args):
    state = read_state(args.state)
    tasks, issues, unknown, exceptional, completed, review, context = [], [], [], [], [], [], []
    by_role, by_status, progress_counts = {}, {}, {}
    seen = set()
    protected = [args.state]
    for index, raw in enumerate(state["tasks"]):
        errors = []
        if not isinstance(raw, dict):
            issues.append({"index": index, "task_id": None, "errors": ["task must be an object"]})
            unknown.append({"index": index, "task_id": None, "fields": ["task_record"]})
            continue
        for field in ("task_id", "role", "status"):
            check_string(raw.get(field), field, errors)
        task_id = raw.get("task_id") if nonempty(raw.get("task_id")) else None
        role = raw.get("role") if nonempty(raw.get("role")) else None
        status = raw.get("status") if nonempty(raw.get("status")) else None
        if task_id in seen and task_id is not None:
            errors.append("duplicate task_id")
        seen.add(task_id)
        for field in ("brief_path", "result_path", "blocker"):
            check_string(raw.get(field), field, errors, nullable=True)
        check_bool(raw.get("review_required"), "review_required", errors)
        signals = raw.get("signals")
        if signals is None:
            signals = {}
        if not isinstance(signals, dict):
            errors.append("signals must be an object or null")
            signals = {}
        normalized = {kind: normalize_signal(signals.get(kind), kind, errors)
                      for kind in ("liveness", "activity", "progress")}
        task = {"task_id": task_id, "role": role, "status": status,
                "brief_path": raw.get("brief_path"), "result_path": raw.get("result_path"),
                "blocker": raw.get("blocker"), "review_required": raw.get("review_required"),
                "signals": normalized, "record_valid": not errors}
        tasks.append(task)
        by_role[role or "unknown"] = by_role.get(role or "unknown", 0) + 1
        by_status[status or "unknown"] = by_status.get(status or "unknown", 0) + 1
        assessment = normalized["progress"]["assessment"]
        progress_counts[assessment] = progress_counts.get(assessment, 0) + 1
        if errors:
            issues.append({"index": index, "task_id": task_id, "errors": errors})
        status_key = (status or "").upper()
        if status_key in COMPLETE_STATUSES or status_key in {"PENDING_ACCEPTANCE", "AWAITING_ACCEPTANCE"}:
            completed.append(task_id)
        if status_key in REVIEW_STATUSES or (status_key in COMPLETE_STATUSES and
                                            ((role or "").lower() == "research" or raw.get("review_required") is True)):
            review.append(task_id)
        if status_key == "NEEDS_CONTEXT":
            context.append(task_id)
        if status_key in {"BLOCKED", "FAILED", "ERROR"} or raw.get("blocker") or errors:
            exceptional.append({"index": index, "task_id": task_id, "status": status,
                                "blocker": raw.get("blocker"), "record_errors": errors})
        unknown_fields = [kind for kind in normalized if normalized[kind]["assessment"] == "unknown"]
        if status_key not in KNOWN_STATUSES:
            unknown_fields.append("status_meaning")
        if role is None:
            unknown_fields.append("role")
        if task_id is None:
            unknown_fields.append("task_id")
        if unknown_fields:
            unknown.append({"index": index, "task_id": task_id, "fields": unknown_fields})
        for field in ("brief_path", "result_path"):
            if nonempty(raw.get(field)):
                protected.append(Path(args.state).resolve().parent / raw[field])
    changed = []
    baseline = "not_provided"
    if args.previous:
        previous = load_json(args.previous)
        previous_errors = []
        check_schema(previous, "previous snapshot", previous_errors)
        if not isinstance(previous.get("tasks"), list):
            previous_errors.append("previous snapshot.tasks must be an array")
        if previous_errors:
            raise CoordError(previous_errors)
        before, after = tasks_by_id(previous["tasks"]), tasks_by_id(tasks)
        changed = sorted(task_id for task_id in set(before) | set(after) if before.get(task_id) != after.get(task_id))
        baseline = "compared"
        protected.append(args.previous)
    output = {"schema_version": 1, "command": "snapshot", "ok": not issues,
              "objective": state["objective"], "objective_complete": {"recorded": state["objective_complete"]},
              "counts": {"input_tasks": len(state["tasks"]), "readable_tasks": len(tasks),
                         "by_role": by_role, "by_status": by_status, "progress_assessments": progress_counts,
                         "completed_pending_acceptance": len(completed), "pending_review": len(review),
                         "needs_context": len(context), "exceptional": len(exceptional), "unknown": len(unknown)},
              "completed_pending_acceptance": completed, "pending_review": review, "needs_context": context,
              "exceptional": exceptional, "unknown": unknown, "task_issues": issues, "tasks": tasks,
              "support_queue_items": len(state["support_queue"]), "delta_baseline": baseline,
              "changed_task_ids": changed,
              "evidence_boundary": "Summarizes records only; checked_record does not authenticate independent provenance or scientific correctness."}
    if issues:
        output["errors"] = ["one or more task records are malformed; readable records are retained"]
    return output, json_text(output), protected


def support_group_key(item, config):
    return (item["family"], item["owner_role"], tuple(sorted(set(item["allowed_write_roots"]))),
            config["model"], config["effort"])


def support_queue(args):
    state = read_state(args.state)
    issues, valid, seen, eligible, manual, assigned, completed, blocked, excluded = [], [], set(), [], [], [], [], [], []
    protected = [args.state]
    output_paths = {}
    for index, item in enumerate(state["support_queue"]):
        label = "support_queue[{}]".format(index)
        errors = []
        if not isinstance(item, dict):
            issues.append({"index": index, "support_id": None, "errors": [label + " must be an object"]})
            continue
        require(item, ("support_id", "status", "family", "read_first", "allowed_write_roots", "expected_outputs",
                       "owner_role", "scientific_identity_changed", "mutates_independent_report"), label, errors)
        check_string(item.get("support_id"), label + ".support_id", errors)
        if nonempty(item.get("support_id")):
            if item["support_id"] in seen:
                errors.append(label + ".support_id is duplicated")
        if not isinstance(item.get("status"), str) or item["status"] not in {"queued", "assigned", "completed", "blocked"}:
            errors.append(label + ".status must be queued, assigned, completed, or blocked")
        if not isinstance(item.get("family"), str) or item["family"] not in FAMILIES:
            errors.append(label + ".family must be an ordinary support family")
        if not isinstance(item.get("owner_role"), str) or item["owner_role"] not in {"author", "reviewer"}:
            errors.append(label + ".owner_role must be author or reviewer")
        check_paths(item.get("read_first"), label + ".read_first", "purpose", errors)
        check_paths(item.get("expected_outputs"), label + ".expected_outputs", "description", errors)
        check_strings(item.get("allowed_write_roots"), label + ".allowed_write_roots", errors)
        for field in ("scientific_identity_changed", "mutates_independent_report"):
            check_bool(item.get(field), label + "." + field, errors)
        check_configuration(item, label, errors)
        declared_paths = {}
        if not errors:
            for entry in item["expected_outputs"]:
                try:
                    key = os.path.normcase(str((Path(args.state).resolve().parent / entry["path"]).resolve()))
                except (OSError, RuntimeError, ValueError) as exc:
                    errors.append(label + ".expected_outputs: invalid path ({})".format(exc))
                else:
                    declared_paths[key] = entry["path"]
        if isinstance(item.get("read_first"), list):
            protected.extend(referenced_paths(item["read_first"], Path(args.state).resolve().parent))
        if errors:
            issues.append({"index": index, "support_id": item.get("support_id"), "errors": errors})
        else:
            seen.add(item["support_id"])
            valid.append(item)
            output_paths[item["support_id"]] = declared_paths
    for item in valid:
        support_id = item["support_id"]
        config = configuration(item, item["owner_role"] == "author", state.get("author_defaults"))
        if item["status"] != "queued":
            {"assigned": assigned, "completed": completed, "blocked": blocked}[item["status"]].append(support_id)
            continue
        if item.get("task_kind") == "research" or item.get("role") == "research":
            excluded.append({"support_id": support_id, "reason": "research_task_not_support"})
            continue
        reasons = []
        if item["scientific_identity_changed"] is not False:
            reasons.append("scientific_identity_changed_or_unknown")
        if item["mutates_independent_report"] is True:
            reasons.append("original_reviewer_required_for_independent_report")
        elif item["mutates_independent_report"] is None:
            reasons.append("independent_report_ownership_unknown")
        if item["owner_role"] != "author":
            reasons.append("reviewer_owned_support")
        if reasons:
            manual.append({"support_id": support_id, "owner_role": item["owner_role"],
                           "reasons": reasons, **config})
        else:
            eligible.append((item, config))
    assigned_writers, queued_writers = {}, {}
    for item in valid:
        if item["status"] == "assigned":
            for key, path in output_paths[item["support_id"]].items():
                assigned_writers.setdefault(key, []).append((item["support_id"], path))
    for item, config in eligible:
        group = support_group_key(item, config)
        for key, path in output_paths[item["support_id"]].items():
            queued_writers.setdefault(key, []).append((item["support_id"], path, group))
    conflict_free = []
    for item, config in eligible:
        reasons, conflicts = [], []
        group = support_group_key(item, config)
        for key, path in output_paths[item["support_id"]].items():
            for other_id, other_path in assigned_writers.get(key, []):
                if "output_conflict_with_assigned" not in reasons:
                    reasons.append("output_conflict_with_assigned")
                conflicts.append({"support_id": other_id, "path": path, "other_path": other_path, "status": "assigned"})
            for other_id, other_path, other_group in queued_writers.get(key, []):
                if group != other_group:
                    if "output_conflict_between_queued_batches" not in reasons:
                        reasons.append("output_conflict_between_queued_batches")
                    conflicts.append({"support_id": other_id, "path": path, "other_path": other_path, "status": "queued"})
        if conflicts:
            manual.append({"support_id": item["support_id"], "owner_role": item["owner_role"],
                           "reasons": reasons, "conflicts": conflicts, **config})
        else:
            conflict_free.append((item, config))
    eligible = conflict_free
    limit = len(eligible) if args.max_items is None else args.max_items
    groups = {}
    for item, config in eligible[:limit]:
        key = support_group_key(item, config)
        if key not in groups:
            groups[key] = {"family": item["family"], "owner_role": item["owner_role"],
                           "allowed_write_roots": list(key[2]), **config,
                           "support_ids": [], "read_first": [], "expected_outputs": []}
        proposal = groups[key]
        proposal["support_ids"].append(item["support_id"])
        for field in ("read_first", "expected_outputs"):
            for entry in item[field]:
                if entry not in proposal[field]:
                    proposal[field].append(entry)
    output = {"schema_version": 1, "command": "support-queue", "ok": not issues, "proposals_only": True,
              "proposals": list(groups.values()), "eligible_count": len(eligible),
              "displayed_count": min(limit, len(eligible)), "remaining_count": max(0, len(eligible) - limit),
              "manual_review": manual, "assigned_skipped": assigned, "completed_skipped": completed,
              "blocked_items": blocked, "excluded": excluded, "queue_issues": issues}
    if issues:
        output["errors"] = ["one or more support queue records are malformed; valid suggestions are retained"]
    return output, json_text(output), protected


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CoordError("arguments: " + message)


def nonnegative_int(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    if number < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return number


def main(argv=None):
    command = None
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        parser = Parser(description=__doc__)
        commands = parser.add_subparsers(dest="command", required=True)
        for name in ("brief", "check-result", "snapshot", "support-queue"):
            child = commands.add_parser(name)
            child.add_argument("--output", help="write generated output atomically; input overwrite is refused")
            if name == "brief":
                child.add_argument("--task", required=True)
                child.set_defaults(handler=brief)
            elif name == "check-result":
                child.add_argument("--result", required=True)
                child.add_argument("--root")
                child.add_argument("--task", help="check task identity and declared completed deliveries")
                child.set_defaults(handler=check_result)
            else:
                child.add_argument("--state", required=True)
                if name == "snapshot":
                    child.add_argument("--previous")
                    child.set_defaults(handler=snapshot)
                else:
                    child.add_argument("--max-items", type=nonnegative_int)
                    child.set_defaults(handler=support_queue)
        args = parser.parse_args(argv)
        command = args.command
        result, content, inputs = args.handler(args)
        if args.output:
            write_output(args.output, content, inputs)
        sys.stdout.write(json_text(result))
        return 0 if result["ok"] else 2
    except (CoordError, OSError, RuntimeError, ValueError) as exc:
        errors = exc.errors if isinstance(exc, CoordError) else [str(exc)]
        sys.stdout.write(json_text({"command": command, "ok": False, "errors": errors}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
