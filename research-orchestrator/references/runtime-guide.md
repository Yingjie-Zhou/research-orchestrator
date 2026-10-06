# 文件简报、回执与运行状态

`scripts/coord.py` 是使用 Python 标准库的本地文件助手。它整理简报、核对回执与实际产物、比较状态、建议支持批次；实际 Codex 查询和派工仍使用当前环境中已获授权的工具。运行助手不意味着任务已派出、科学成果已接受或项目已完成。

助手提供文件简报、结构化回执检查、状态投影、支持批次建议及事件信号整理。职责路由只作为合同数据保存和展示；助手不包含自动 DAG、幂等派工、外部 Codex CLI 或模型降档，也不会发送消息、建立自动化或终止任务。

完整工作单元可通过`execution_plan_ref`引用 [连续工作单元](continuous-work-units.md) 的小执行计划；`work_unit.py`生成连续步骤、具名接续和真实收件者说明及投递参数。直接执行/消息权限由人类授权与原合同决定，助手不作授权或科学接受。

## 开始使用

新项目将 `assets/task-brief.json`、`assets/author-result.json`、`assets/project-state.json` 复制到项目内的协调目录，再填写当前目标和必要字段。模板中的 `null` 与空数组表示尚未取得或尚未填写；不能直接作为执行成功的证明。

已有项目从原主控状态生成小投影，保留原状态及历史索引。只映射当前目标、任务身份与状态、简报/回执路径、阻塞、信号和支持队列；不要为了使用助手重写旧 schema 或复制完整聊天历史。状态文件由指定所有者维护，快照另存，避免覆盖原状态或独立报告。

作者默认 `gpt-6.1-sol/xhigh`，包括简单支持任务。审查员与顾问沿用各自已核实的既定配置。把模板用于 `review` 时须填入对应审查配置；作者承担 `integration` 时仍明确填写作者配置。记录实际工具配置和启动回执，不能从模板字段推断已实际使用该模型。

执行顺序：

1. 由现有作者或已授权支持角色填写任务 JSON，生成并保存 Markdown 简报；通过已授权工具给执行者传简报绝对路径及必要读取入口。
2. 执行负责人读取必要输入、按写入范围实施、自检与修复，把完整报告写入 `report_path`、短回执写入 `result_path`，向指定接收方交付可整体使用的报告/回执/产物包及引用。
3. 程序或支持角色完成文件与合同的机械核对；既有验收负责人结合真实来源、实际内容和独立审查接收任务范围，指定状态所有者更新状态。集成作者直接利用已审范围完成共同链，不逐项转给主控重新整理。
4. 程序或支持角色生成快照并比较 `changed_task_ids`；主控查看变化摘要、真正需要其判断的决定请求及最终证据。未知或冲突由对应负责人定向查询，快照不代独立审查。

小项目沿用现有角色扁平分工，不新增管理岗位。集成作者对共同链实施和交付负责，不承担全体专家逐轮管理、集中打包或重复科学审查；各执行负责人交完整包，避免把主控瓶颈转移到集成作者。

## `brief`：文件简报

接口：`brief --task TASK.json [--output FILE.md]`。

任务 JSON 使用模板中的字段：

| 字段 | 填写方式 |
|---|---|
| `schema_version`、`task_id`、`task_kind` | 版本为 `1`；任务 ID 非空；类型为 `research/support/review/integration` |
| `objective` | 当前可验证目标及相对已有工作的增量，不写预期成功结论 |
| `read_first` | 对象数组，每项为 `{"path": "绝对路径", "purpose": "为何必要"}`；只列任务必要输入 |
| `allowed_write_roots` | 允许写入目录的字符串数组；按所有权选择，避免共享修改冲突 |
| `expected_outputs` | 对象数组，每项为 `{"path": "绝对路径", "description": "实际交付"}` |
| `done_criteria`、`global_constraints` | 字符串数组；写可核对的完成条件，以及科学身份、预算、停止条件和审查等适用约束 |
| `responsibility` | 可选责任路由对象，仅新合同存在接收、验收或升级歧义时填写；旧任务无需迁移 |
| `model`、`effort` | 合同请求使用的已授权配置；作者用默认值，独立审查另按配置；实际执行值须有启动证据 |
| `report_path`、`result_path` | 完整报告与结构化短回执的绝对路径，分别保存 |

`task_id`、`objective`、输入、写入范围、交付与验收条件以及报告/回执路径须按任务填妥，才可实际派工。没有某类输入时可保留空数组，并在合同说明理由；空写入范围不能被解释成任意位置可写。

`responsibility` 引用已有负责人：`execution_owner` 负责执行、自检、修复和完整交付；`delivery_receiver` 接收完整包；`acceptance_owner` 是本任务范围内的接收与验收负责人，项目总体终点仍由主控判断；`review_owner` 指向实际原审查员。任务验收负责人不能替代审查员的独立科学判断，程序也不能认证来源真实性或科学接受；这些仍依真实执行与审查证据及对应负责人。

`routine_decisions` 是原授权、合同和预算内可本地决定的必要读取、定位修复、作者元数据更正等事项。`escalate_to` 与 `escalate_when` 只记录跨合同冲突、科学问题/模型/目标变更、硬预算授权或总体终点等真正升级条件，不把所有日常事项上交。负责人尚未明确时保留 `null`，决策清单尚未定义时保留空数组；可省略整个对象，不能据此创建新岗位或放宽旧硬限制。独立报告仍只由原审查员维护。

简报列出路径与用途，不载入长历史。必要依赖补读按现行授权和科学合同判断并留痕，`read_first` 不是固定文件数门槛。四个命令均在 stdout 返回 JSON：不带 `--output` 时简报放在 `brief_markdown`；带参数时把 Markdown 保存到指定文件，并返回输出路径与结果。

`brief` 的 `ok: true` 只说明结构与渲染通过，不检查输入是否存在、路径是否绝对、输出是否属于允许写入范围或预算控制是否可执行。合同负责人在实际派工前确认这些任务相关条件，可复用已核对证据；占位字段和模型请求不能当作合同已就绪、实际配置或已派出证明。

## `check-result`：工作回执与产物身份

接口：`check-result --result RESULT.json [--root ROOT] [--task TASK.json]`。

执行者填实 `task_id`、`summary`，并选择 `work_status`：

- `DONE`：任务交付条件完成，至少列一个可核对的实际产物。
- `DONE_WITH_CONCERNS`：已交付，但存在会影响使用的限制；在 `concerns` 中明确范围。
- `NEEDS_CONTEXT`：缺少必要上下文；用 `missing_inputs` 指出最小缺项及用途。
- `BLOCKED`：当前无法执行；在摘要与完整报告中给出阻塞类别、证据、解除动作和仍可完成的范围。

`artifacts` 每项为 `{"path": "产物路径", "sha256": "实际文件的 SHA-256"}`。相对产物路径基于 `--root`；省略时基于回执所在目录。所有声明的产物均应存在并具备实际哈希，不能把预计路径或占位哈希当成已产出。

`validation` 保存 `status` 与 `evidence_refs`；尚未运行时保持 `not_run` 和空数组。`concerns`、`missing_inputs`、`review.accepted_scope`、各处 `evidence_refs` 为字符串数组。`scientific_identity_changed` 为明确的 `true/false` 或尚未确定的 `null`，不能以缺值推定身份未变。成本字段 `cpu_s/native_wall_s/model_cost` 只填实际计量数值，未计量保持 `null`，不填零。

`review` 初始为 `not_reviewed`、空范围与 `null` 报告引用。作者不能自写科学 `ACCEPT`，不能修改独立报告；已有审查仅引用真实来源和实际接受范围，由指定验收负责人核对。结构与 SHA 校验只证明字段及文件身份，不能认证科学结论、审查独立性或端到端目标达成。

返回的 JSON 包含工作状态、`artifact_identity`、`validation_record`、`review_record`，科学接受保持 `science_acceptance: "not_decided"`。需要核对交付是否对应原简报时提供 `--task`：工具核对任务ID，以及完成声明对应的 `expected_outputs` 和完整 `report_path` 是否存在，缺项明确列出并返回失败。未提供时明确原任务合同尚未核对；一个原有文件哈希匹配不能证明新的合同已经完成。它不自动判断 `done_criteria` 的内容或认证独立审查来源，验收负责人结合实际产物内容、真实执行轨迹与相应审查做接受判断，主控依据最终证据判断总体终点。

## `snapshot`：小投影与三种信号

接口：`snapshot --state STATE.json [--previous SNAPSHOT.json] [--output FILE.json]`。

状态根字段为 `schema_version/objective/objective_complete/author_defaults/tasks/support_queue`。初始 `objective_complete` 为 `false`。每个 `tasks` 条目填写 `task_id/role/status/brief_path/result_path/blocker/signals`；角色与状态使用项目原有语义，阻塞尚未确认时用 `null`，不要编造运行状态。可选 `review_required: true/false/null` 记录明确的待审要求；研究完成默认待审，纯支持完成只待轻量接收，其他角色仅显式待审状态或 `review_required: true` 才进入待审列表。该列表不改变原科学合同的审查要求。

每项任务的 `signals` 分别记录 `liveness/activity/progress`，每种信号均有以下结构；首次没有证据时三个信号都用未知值：

```json
{
  "value": null,
  "source": null,
  "observed_at": null,
  "evidence_refs": [],
  "basis": null
}
```

| 信号 | 证据与解释 |
|---|---|
| `liveness` | 当前执行轨迹或可信状态说明任务是否仍在运行；没有可靠观测则未知 |
| `activity` | 当前观察区间的日志、回复或执行活动；仅有新日志可说明活动，不能自动说明成果进展 |
| `progress` | 已核对产物或已接受检查点；`true` 必须有 `basis: "checked_artifact"` 或 `"accepted_checkpoint"`，并记录 `source` 与非空 `evidence_refs` |

`false` 也须有对应观测依据；无来源的非空真假值只保留为 `claimed`，不表示已经观察到健康运行、终止、无活动或无进展，缺证据的 `null` 在快照中保持 `unknown`。非空 `observed_at` 须为合法带时区时间（可用 `Z`），无效时间作为该条目数据问题报告，其他可读任务保留；没有时间证据仍可用 `null`。不拿文件修改时间冒充计算起点，也不从时间字段自动推出沉默超时。`checked_artifact` 只表明产物被核对；`accepted_checkpoint` 须指向真实已接受范围，两者均不代独立审查。

命令输出归一化任务、信号 `assessment` 与 `changed_task_ids`。首次没有 `--previous` 时建立基线；后续比较读取上次快照。只更新 `observed_at` 不算成果变化，也不会仅因此把任务列入变化清单。即使出现变化，主控仍判断它是状态、阻塞、活动还是实际成果增量。

## `support-queue`：建议合并小项

接口：`support-queue --state STATE.json [--max-items N]`。

`support_queue` 每项包含：

| 字段 | 可用值或结构 |
|---|---|
| `support_id`、`status` | 非空 ID；状态为 `queued/assigned/completed/blocked` |
| `family` | `handoff/inventory/metadata/log_summary/directory_check` |
| `read_first`、`allowed_write_roots`、`expected_outputs` | 与任务简报相同的数组结构 |
| `owner_role`、`model`、`effort` | 所有者为 `author/reviewer`；填实际授权配置 |
| `scientific_identity_changed`、`mutates_independent_report` | 各为 `true/false/null`；未知不能当作 `false` |

普通作者支持项只有明确为 `author` 且两项身份/独立报告标志均为 `false` 时，才能建议合并。按 `family`、允许写入范围的所有权和模型/努力配置兼容分批。作者默认仍为 `gpt-6.1-sol/xhigh`；减负来自合并交接和适当验收。

支持者更新自己所有的派生索引，且原报告及接受范围不变时，不属于改独立报告。原索引归属不明则先准备候选更正；具体报告与索引边界见 [职责与减负](role-boundaries.md)。队列仍按实际写入对象及其所有权记录，不能用派生索引名义覆盖原报告。

`assigned` 项不重复建议；`completed` 项不再派工；`blocked` 项先判断阻塞。独立报告归原审查员，未知所有权/影响或涉及科学身份变化的项转 `manual_review`，不能由普通作者支持包承接。`--max-items` 只限制本次显示或建议批次，不限制科学任务必要读取。输出含 `proposals_only: true`、`proposals`、`manual_review`、`assigned_skipped` 与 `remaining_count`；不实际派工或更新队列。个别坏条目列入 `queue_issues`、返回 `ok: false` 并排除该项，但合法建议仍可读取；主控不能把部分可读误称全队列检查通过。

建议前核对声明的输出路径：与已 `assigned` 项重叠的待派项转人工处理，保留冲突ID与路径；没有冲突的项仍可建议。不同待派批次若声明相同输出也应明确提示，不自动并发写入。该检查仅覆盖已记录路径，不能认证实际所有权或代替全局文件锁。

并发计划共同考虑研究、审查与支持任务，先保障目标关键路径和原审查必要资源。能合并的小项给同一可用执行者；有空位才派出合适批次，不为了处理整理工作打断健康研究。真正派出成功后，由状态所有者登记 `assigned` 和实际任务回执。

## 异常接续

`NEEDS_CONTEXT` 时补足已说明的最小必要输入与路径，在原授权内续接，不重新塞入全部历史。`BLOCKED` 时区分执行环境/资源、流程与所有权、实现/数值、模型有效性、信息不足，再选择修复、替代方法或停止该方法；一项阻塞不自动冻结无依赖任务。

静默只表示未取得新消息。没有活动证据时保持信号未知，先用已授权工具做有界状态查询或必要诊断；不能据静默自动杀任务、重复派工或推断科学失败。可靠硬预算与明确停止条件继续生效。

## 跨平台运行

先解析本机已部署技能的 `scripts/coord.py` 绝对路径，再核对所选解释器版本。要求 Python 3.8+，仅用标准库，不安装额外依赖。先检查实际调用的解释器版本；部署其他主机时分别核对版本和安装路径。

以下项目路径是待替换示例；先填实任务/回执/状态文件。首次快照省略 `--previous`，后续保留旧快照并使用另一输出文件。

PowerShell：

```powershell
$coord = (Join-Path $env:USERPROFILE '.codex\skills\research-orchestrator\scripts\coord.py')
$coordPython = (Get-Command python -ErrorAction Stop).Source
& $coordPython --version
& $coordPython $coord brief --task 'D:\项目\.coord\task.json' --output 'D:\项目\.coord\brief.md'
& $coordPython $coord check-result --result 'D:\项目\.coord\result.json' --root 'D:\项目' --task 'D:\项目\.coord\task.json'
& $coordPython $coord snapshot --state 'D:\项目\.coord\state.json' --previous 'D:\项目\.coord\snapshot.previous.json' --output 'D:\项目\.coord\snapshot.current.json'
& $coordPython $coord support-queue --state 'D:\项目\.coord\state.json' --max-items 4
```

Linux/macOS：

```sh
coord="$(cd '/path/to/research-orchestrator' && pwd)/scripts/coord.py"
coord_python=python3
"$coord_python" --version
"$coord_python" "$coord" brief --task '/project/.coord/task.json' --output '/project/.coord/brief.md'
"$coord_python" "$coord" check-result --result '/project/.coord/result.json' --root '/project' --task '/project/.coord/task.json'
"$coord_python" "$coord" snapshot --state '/project/.coord/state.json' --previous '/project/.coord/snapshot.previous.json' --output '/project/.coord/snapshot.current.json'
"$coord_python" "$coord" support-queue --state '/project/.coord/state.json' --max-items 4
```

各命令 stdout 为 JSON，可保存供主控读取；`--output` 的简报是 Markdown，快照是 JSON。命令退出失败或返回 `ok: false` 时保留错误依据，不能把输出文件存在推定为检查通过。

## 稳定接收与时钟报告

重复交接使用 scripts/receiving.py，支持现有AUTHOR_RESULT声明的目录或显式manifest；输出一份decision_summary、身份/变化及所有者缺项路由，原BLOCK仍可接收为异常包，科学接受始终not_decided。scripts/receiving_ingress.py默认只预览，原状态所有者显式提交时按两个真实SHA校验版本，仅登记routine_receptions，不更改科研接受、预算或调度。scripts/clock_report.py区分显式程序执行、连续硬时钟、软节点和协调等待，报告不追加资源或重解释旧期限。接口、模板、字节桥边界和迁移验证见 [稳定接收与分开计时](receiving-and-clocks.md)。
