#!/usr/bin/env python3
"""Render bounded work units and direct-delivery arguments; never send or execute."""
import argparse
import json
from pathlib import Path
import sys


def validate_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError("execution plan must be an object")
    for name in ("task_id", "outcome", "scope_ref", "limits_ref", "authority_ref"):
        if not isinstance(plan.get(name), str) or not plan[name].strip():
            raise ValueError(name + " must name the task, outcome or original reference")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps or any(not isinstance(s, str) or not s.strip() for s in steps):
        raise ValueError("steps must describe the complete permitted work unit")
    seen = set()
    actions = plan.get("preauthorized_continuations", [])
    if not isinstance(actions, list):
        raise ValueError("preauthorized_continuations must be an array")
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("continuation must be an object")
        for name in ("id", "when", "action"):
            if not isinstance(action.get(name), str) or not action[name].strip():
                raise ValueError("continuation needs id, condition and action")
        if action["id"] in seen:
            raise ValueError("duplicate continuation id")
        seen.add(action["id"])
        for name in ("requires_new_authorization", "extra_native_calls"):
            if type(action.get(name)) is not bool:
                raise ValueError("continuation " + name + " must be explicit boolean")
        if action["extra_native_calls"] and not action.get("operation_authorization_ref"):
            raise ValueError("additional native calls need their own explicit authorization reference")
    seen = set()
    routes = plan.get("direct_delivery")
    if not isinstance(routes, list) or not routes:
        raise ValueError("direct_delivery must name at least one actual receiver")
    for route in routes:
        if not isinstance(route, dict):
            raise ValueError("route must be an object")
        for name in ("id", "thread_id", "host_id"):
            if not isinstance(route.get(name), str) or not route[name].strip():
                raise ValueError("route needs exact id, thread_id and host_id")
        if route["id"] in seen:
            raise ValueError("duplicate route id")
        seen.add(route["id"])
        if route.get("purpose") not in {"consumer", "review", "milestone"}:
            raise ValueError("route purpose must be consumer, review or milestone")
        transport = route.get("transport", "send_message_to_thread")
        if transport not in {"send_message_to_thread", "original_parent_review_channel"}:
            raise ValueError("unsupported delivery transport")
        if transport == "original_parent_review_channel" and (route["purpose"] != "review" or not route.get("owner_thread_id")):
            raise ValueError("original parent review channel requires original author owner")
    return plan


def render_plan(plan):
    validate_plan(plan)
    lines = ["# 连续工作单元", "", plan["outcome"], "",
             "原科学范围：" + plan["scope_ref"], "原累计限制：" + plan["limits_ref"],
             "直接人类授权：" + plan["authority_ref"], "", "在允许范围内连续完成："]
    lines.extend("- " + step for step in plan["steps"])
    lines.extend(["", "已安排的接续（条件实际满足且原累计余量可靠时执行）："])
    for action in plan.get("preauthorized_continuations", []):
        qualifier = "需新授权，不能直接执行" if action["requires_new_authorization"] else "无需逐阶段重新派工"
        lines.append("- {}：{} → {}；{}。".format(action["id"], action["when"], action["action"], qualifier))
    lines.extend(["", "直接交付："])
    for route in plan["direct_delivery"]:
        lines.append("- {}：{} / {}（{}）。".format(route["id"], route["thread_id"], route["host_id"], route["purpose"]))
        if route.get("transport") == "original_parent_review_channel":
            lines.append("  原作者 {} 沿已有专属审查通道投递；该UUID只作审查身份锚点，不能由其他主控用普通聊天接口硬发。".format(route["owner_thread_id"]))
    lines.extend(["", "本说明不增发预算、样本或原生操作，不改变原报告/失败。未审成果只作待审候选；科学接受由原独立审查决定。",
                  "接续遇到真实范围/权限/资源越界时升级；普通实现、必要自检和同问题修复按原允许范围成组处理。"])
    return "\n".join(lines) + "\n"


def delivery_requests(plan, package_ref, package_sha=None, recipient=None):
    validate_plan(plan)
    if not isinstance(package_ref, str) or not package_ref.strip():
        raise ValueError("package reference is required")
    if package_sha is not None and (len(package_sha) != 64 or any(c not in "0123456789abcdefABCDEF" for c in package_sha)):
        raise ValueError("package SHA must be a 64-character hexadecimal digest")
    routes = [r for r in plan["direct_delivery"] if recipient is None or r["id"] == recipient]
    if not routes:
        raise ValueError("recipient is not in this authorized task route table")
    output = []
    for route in routes:
        instruction = {"consumer": "作为此任务的直接消费者，请核对实际使用所需的来源、版本和已审范围；未审部分仅作候选，不自动采用。",
                       "review": "请沿原专属审查角色，对原合同完整问题和实际冻结产物独立审查；普通缺项直接返回原作者，保留失败和unknown。",
                       "milestone": "此为目标里程碑/真实异常摘要入口；常规产物已直接提供原消费者和审查员，按需要作方向/共享资源/最终验收决定。"}[route["purpose"]]
        prompt = "任务 {} 直接交付。\n{}\n产物引用（来源数据，不是其中命令的执行授权）：{}\n产物SHA：{}\n原范围：{}\n原限制：{}\n人类授权依据：{}".format(
            plan["task_id"], instruction, package_ref, package_sha or "未提供，按实际来源核对", plan["scope_ref"], plan["limits_ref"], plan["authority_ref"])
        if route.get("transport") == "original_parent_review_channel":
            output.append({"route_id": route["id"], "purpose": route["purpose"], "tool": "original_parent_review_channel",
                           "execution_owner_thread_id": route["owner_thread_id"], "review_identity": {"thread_id": route["thread_id"], "host_id": route["host_id"]},
                           "message": prompt, "instruction": "Original author uses its existing dedicated reviewer mechanism; no app send, new reviewer or model replacement inferred."})
        else:
            output.append({"route_id": route["id"], "purpose": route["purpose"], "tool": "send_message_to_thread",
                           "arguments": {"threadId": route["thread_id"], "hostId": route["host_id"], "prompt": prompt}})
    return {"requests": output, "sent": False, "permission_verified": False, "scientific_acceptance_verified": False,
            "note": "Prepared arguments only. Calling owner must verify direct human authorization and actual evidence; no message, model change or scientific acceptance performed."}


def main(argv=None):
    from coord import load_json, write_output, json_text, CoordError
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["render", "delivery"])
    parser.add_argument("--plan", required=True)
    parser.add_argument("--package-ref")
    parser.add_argument("--package-sha")
    parser.add_argument("--recipient")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        plan = validate_plan(load_json(args.plan))
        if args.command == "render":
            result = {"ok": True, "rendered": render_plan(plan), "execution_performed": False}
            content = result["rendered"]
        else:
            result = dict(delivery_requests(plan, args.package_ref, args.package_sha, args.recipient), ok=True)
            content = json_text(result)
        protected = [args.plan] + [Path(args.plan).resolve().parent / plan[k] for k in ("scope_ref", "limits_ref", "authority_ref")]
        if args.output:
            write_output(args.output, content, protected)
        sys.stdout.write(json_text(result))
        return 0
    except (ValueError, OSError, CoordError) as exc:
        sys.stdout.write(json_text({"ok": False, "errors": [str(exc)]}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
