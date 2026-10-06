# 状态与合同

这些结构是新项目的参考起点。按实际风险选取相关字段；同机短任务不必具备远程线程、Git父链或完整资源分账，项目不能因为没有这些无关字段被判失败。已有项目保留自己的 schema 和证据格式，映射语义即可。示例中的 null 是尚未取得的值，不能当作零或执行成功。可能耗用受限计算资源的操作，派工前落实预算及控制。

本文说明完整研究合同与审查语义。需要减少调度上下文时，使用 [轻量协作工具](runtime-guide.md) 的简报、作者回执和状态模板；其机器字段由模板与工具维护，不要求下面的概念示例原样成为程序输入。简报通过必要输入引用完整预注册，不取代冻结原任务与审查 coverage。

## 主控状态

维护一个明确的状态所有者，可以是已授权的现有支持执行者；主控保留总体验收责任，不必亲自整理所有字段。建议将当前摘要放在 `MASTER_STATE.json`，任务合同放在 `TASK_ASSIGNMENTS.json` 或独立文件，审查约定放在 `REVIEW_POLICY.json`。避免三份文件复制整段历史；它们相互引用。

```json
{
  "schema_version": 1,
  "objective": null,
  "required_evidence_level": null,
  "final_acceptance_criteria": [],
  "objective_complete": false,
  "authorization_evidence": [],
  "state_owner": null,
  "integration_owner": null,
  "accepted_baseline": null,
  "tasks": [],
  "open_failures_and_unknowns": [],
  "next_action": null,
  "history_index": [],
  "updated_at": null
}
```

每项任务保留 `task_id`、原合同引用/身份、负责人、实际主机/路径、执行机制、原任务/轮次标识、最新状态及查询游标、冻结输入/结果、审查引用和下一信息判断。执行机制不同允许不同字段，不编造 threadId、代理 ID、提交号或成功状态。

如共享状态会被异步更新，记录读取时的版本；更新前核对版本，防止旧快照覆盖新任务。更新只涉及本轮确认的字段，已冻结源、报告和既有失败引用保留。

## 派工合同

一个合同覆盖一个完整、有限、可以被反驳的比较。接口诊断只有在它是具体阻塞时才单独成为任务。

把相邻实施、自检、原允许的有限验证和同问题修复纳入同一完整工作单元，并在派工时列出具名接续动作及其条件、原累计限制和直接消费者/原审查员。条件满足时作者自行接续；尚未授权的新问题才由主控另行形成合同。现有格式可用小侧文件承接，见 [连续工作单元](continuous-work-units.md)，不追溯改写冻结科学原文。

指明执行者、交付接收者、任务接收判断者与独立审查员。集成作者直接执行共同链并处理必要组合问题；其他专家的日常往返由各自合同的接收者处理。允许的依赖补读、修复和元数据更正交给对应所有者，目标/模型改变、跨合同取舍或新增权限才升级。按 [职责与减负](role-boundaries.md) 分配，已有角色足够时不新设管理层。文件简报可用可选 `responsibility` 表达；旧合同语义清楚则无需补填。

简单执行支持不要求构造科学比较：可以用短合同记录输入、所属负责人、允许修改位置、输出和验收方式，沿用用户指定作者配置。清单/哈希核对以差异表和真实文件身份交付，交接包以可打开包和内容验证交付，作者元数据更正以差异及科学身份未变的证据交付；仅“已完成”的文字回执不足。多个相关小项可同包，不为每个字段创建一个任务。

合同明确哪些是不可改变的约束，哪些是可在原范围与预算内调整的默认值。没有显式硬限制时，必要依赖补读、同一冻结来源上的小核验、只改元数据和轮询间隔调整可由执行者判断并简记原因；改变模型、样本、观察口径、硬预算或对外动作必须遵循原授权。

```json
{
  "task_id": null,
  "objective": null,
  "information_increment": null,
  "owner": null,
  "execution": {"host": null, "workspace": null, "model": null, "effort": null},
  "input_manifest": null,
  "baseline_identity": null,
  "common_contract": {
    "version": null,
    "geometry": null,
    "units": null,
    "initial_state": null,
    "physical_time": null,
    "observation_operator": null,
    "population_and_denominator": null
  },
  "necessary_dependencies": [],
  "declared_assumptions_and_domain": [],
  "pilot": null,
  "budget": {
    "cumulative_cpu_s_hard": null,
    "peak_rss_mib_hard": null,
    "native_wall_s_hard": null,
    "preparation_review_seal_minutes_soft": null,
    "history_or_sample_cap": null,
    "repair_stop_conditions": [],
    "repair_attempt_cap_if_needed": null,
    "funding_or_authorization": null,
    "enforcement_method": null
  },
  "stop_or_turn_conditions": [],
  "requested_scope": [],
  "deliverables": [],
  "review_contract": null
}
```

`requested_scope` 使用稳定 IDs，并逐项写出问题、可观测证据和适用层级。保留原问题，不能完工后缩成容易通过的小问题。新干预必须保留固定条件和允许变化；共同随机创新须保持各臂边缘随机律，不能强迫碰撞、源或结局相同。

输入清单记录被选执行环境的因果依赖闭包及其身份，必要时使用内容哈希。依赖可按明确因果需要补充并留痕；没有依据时不进行全机器盘点。身份一致不能证明消费者实际使用它，须有真实执行证据。

固定读文件数只在来源、隐私或真实资源风险确有要求时采用。清单遗漏一个同版必要头文件时，按原规则登记补充；若它只是允许范围内的依赖补读，无须重开科学任务。新发现依赖改变了实际运行版本或源语义时，重冻受影响链并核对结论。历史严格合同中已经发生的越界仍保留，不能用新默认值回溯洗掉。

先形成并保存合同全文，再实际派工。派工回执绑定原合同身份、接收方、实际任务标识、时间和生效配置。启动失败记录错误，不能将计划条目填为 running。

## 审查与交付

作者提交：原任务与 scope、冻结输入/代码/声明身份及父链、输出清单、复现入口、原始失败和累计成本。审查员在独立报告位置记录：

```json
{
  "task_id": null,
  "original_task_identity": null,
  "science_identity": null,
  "science_parent": null,
  "reviewer_execution_evidence": null,
  "verdict": null,
  "coverage": [],
  "accepted_scope": [],
  "original_failed_gates": [],
  "unknowns_and_conditions": [],
  "cost_ledger": null,
  "previous_reviews_and_repairs": []
}
```

完整审查的 coverage 保留问题ID、状态、证据、条件和限制，普通短任务可用等价的简表。状态表达 established、failed、unknown、not_attempted 或 out_of_scope。整个原任务均须覆盖，即使大部分尚未完成。

报告分别冻结自身身份并关联被审科学身份，避免自引用哈希。保留审查员真实启动、权限/模型配置和完成输出；作者自写的“审查通过”或完成文件不充分。

元数据缺项先核对可直接观察的原报告字节、审查员完成轨迹和科学身份。若足以唯一关联，可由对应所有者添加更正记录继续验收，不要求作者重算科学结果或重新做整组审查；若关联仍无法建立，则仅将相关范围标为来源未知/未接受。审查员新增必要小检查按其实际证据和成本纳入报告，除非它违反明确硬限制，否则不因未预列便判流程失败。

典型状态流：

`planned → dispatched → running → frozen → reviewed → accepted / accepted_with_limits / unaccepted_exception`

`blocked_by_review → justified_repair → refrozen → same_reviewer_new_report`

这些是状态语义，不要求工具使用同名字段。支持执行者或程序准备身份/来源/范围核对材料，指定接收者结合真实轨迹核对，不能凭结构检查认证来源或科学结论。集成作者另核共同契约与实际调用链；主控据最终证据链及真正升级事项作总体验收，不重复每组自检与科学审查。accepted_with_limits 只集成 accepted_scope，未决项目留在总体状态。

## 成本和下一信息

成本区分实耗、硬上限、预留及未知。累计包含准备/输入处理、失败、修复、冻结、审查及受控执行；CPU 与墙钟不可互相替代。来自可信执行起点的时间可以标为已知，文件 mtime/ctime 不能冒充作者或计算开始时间。

采用足以证明相关硬上限和说明投入的计量粒度。已有可靠执行控制和余额时，其他成本尚未精细计量可以列 unknown；不要为了补精度无限读取旧日志。只有相关硬上限的余额无法可靠确定时，才停止可能超额的操作。格式修正保留实际成本，不消费未运行的科学样本，也不重置累计账本。

下一信息判断只需回答：

1. 已回答的问题与影响的目标结论。
2. 下一项可区分的假说或缺失因果连接。
3. 采用现有记录、完整链试验、定向诊断或替代方法的依据。
4. 最小依赖、有限成本、可执行下一动作；若停，停止哪个方法及何时重评。

不要给“待其他组”“待实测”一个无限期通用状态。若依赖确属必要，给出明确生产者、输入范围和触发动作；除此之外的条件研究仍按信息价值选择。

## 明确接收及时间入口

新合同写清包接收者及其稳定工具/结果路径；支持处理常规身份、元数据与缺项，主控保留重大冲突和终点验收。状态提交绑定读取版本，拒绝包作为unaccepted_exception接收而非要求非空accepted_scope。程序执行硬墙钟、明确连续硬墙钟、准备/审查软节点和协调等待分别定义；未来分类不追溯清除既有连续期限。具体字段采用 [稳定接收与分开计时](receiving-and-clocks.md)，无关短任务不强迫补全。
