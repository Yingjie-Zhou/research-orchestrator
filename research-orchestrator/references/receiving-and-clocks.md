# 稳定接收与分开计时

用于重复交接、拒绝包接收或准备/审查时间引起机械停转的项目。继续使用原科学合同和真实来源；读取校验工具不修改原件、独立报告、主控状态或执行权限。登记入口仅允许原已授权状态所有者显式提交机械接收记录。

## 一次接收，按所有者处理缺项

支持执行者运行稳定入口，发布一份接收结果：文件身份、原审查结论、缺项及对应所有者、相对上次同任务的变化、原件引用。主控先读其中 decision_summary 和 issues；涉及科学身份、跨合同冲突、资源/权限改变或最终终点时再展开原证据。程序的 READY 仅说明声明文件与关系完成机械核对，科学接受始终 not_decided。

支持者拥有派生索引和接收结果，可在自己的目录修正路径、字段映射和运输字节说明。作者维护原任务/代码/自有元数据，审查员维护原独立报告。原件无法唯一绑定或存在真实科学冲突时保持未接受并交相应接收者；不可通过重写原报告消除缺项。

拒绝、失败或未尝试成果也是可接收的完整异常包。原 BLOCK/空 accepted_scope 必须保留，不为让接受型校验器通过而修改它们。包身份 READY 与科学拒绝可以同时成立。

新任务明确接收角色和实际入口。状态仍由原所有者维护；支持者或程序给出绑定当前状态版本的候选更新，由已授权的版本检查入口提交。不能因主控拥有状态写入权限，就让主控重新拼包、重写校验或逐条补元数据。没有授权入口时记录缺口，由现有主控建立，不让支持者自行取得权限或新增管理层。

## receiving.py

已有支持包可直接使用，不改其 schema 或原文件：

    python receiving.py --support-dir /project/support/current --receipt-sha <原回执SHA> --output /project/support/current/RECEIVING_PACKET.json

程序只读取该目录内 AUTHOR_RESULT.json 明确声明的产物和唯一原 review 引用。适配状态/报告字段只发生在派生接收结果；异常布局用显式 manifest，不能靠文件名猜测哪个报告是权威版本。receipt-sha 来自对应可信交付轨迹；未提供时显示调用者未认证回执，不能借其文件身份宣称真实独立来源。

### 由原状态所有者提交机械登记

receiving_ingress.py 默认只预览。原状态所有者可使用当前 state 与接收 packet 的真实SHA调用；仅 --commit 会原子提交 routine_receptions 登记。它不触碰研究任务接受范围、预算、失败历史、调度或总目标。重复同包幂等，同任务不同包不覆盖原历史；状态版本或包身份变化则拒绝并重新准备。此入口不认证调用者、不授予新权限，旧写入入口由原状态所有者串行协调，其锁不能约束任意遗留写入程序。科学接受及审查来源的实际身份仍走原入口。

    python receiving_ingress.py --state MASTER_STATE.json --packet RECEIVING_PACKET.json --expected-state-sha <当前状态SHA> --expected-packet-sha <包SHA>

支持者给出已有可信轨迹绑定的包，主控确认真实来源与接收任务后，经固定入口提交一次机械登记，不再手写逐轮接收脚本。缺项包返回所有者，不借登记升级为 READY。登记后按当前派生摘要消费该记录，避免又在另一路重新拼包或将 READY 当科学接受。

其他项目使用 assets/receiving-manifest.json：

    python receiving.py --manifest packet.json --root /project/owned-package --previous previous-result.json --output current-result.json

manifest 字段：

- task_id：接收任务ID，不混合研究任务ID、支持任务ID与运行turn。
- artifacts：每项 id/path/sha256，可写 role 和 owner；只列当前交付必要证据，不为使用工具重新全量搬入历史。路径限定在调用者给定 root 内，禁止越界和覆盖原输入。
- review：artifact 指向原报告ID，verdict_pointer/accepted_scope_pointer 为 JSON Pointer。原拒绝无接受范围属于正常 reviewed_exception 包。
- bindings：明确同语义的字段对应，每项 label、left/right（artifact/pointer）及 kind。exact 比较原值；review_cycle 只用于明确的复审周期，可比较数值2与FIX2。不可将请求冻结 revision=1 与报告复审周期FIX2错误地当作同一字段。@sha256 指向本次实际计算的原文件SHA。
- coverage：可选 report_artifact/pointer/id_key/original_scope_ids，检查完整原范围结构；它不检查某范围科学成立。

只在同任务之前的接收结果上生成差分；不同任务明确 baseline_compatible=false，不用标签相同冒充科学身份相同。原 SHA 和变化列表保留。稳定既有科学证据通过原已审入口引用，新身份/新声明才核受影响链；无变化心跳不重跑接收工具。

对于明确的 UTF-8 元数据或运输文本，可在某项设置 transport：counterpart_path、counterpart_sha256 和 rule=utf8_crlf_lf。两侧原SHA分别核对，仅比较CRLF到LF后的文本身份；BOM、裸CR、空格及其他字节均保留。源码、科学输入/输出、独立报告不得借该模式放宽其原字节身份。证明写在自有派生结果，永不改原件或替换任一原SHA。未知运输原因仍为缺项。

返回 package_status、package_kind、artifact_identity、bindings、review_record、changes、issues 和 decision_summary。issues 返回原所有者，旧错误与修正引用保留；原 review 结论、全 scope、失败、成本与 unknown 不缩窄。工具不认证审查独立性、实际消费者或最终科学结论；对应接收者依据真实轨迹判断。

## 工程修复按信息价值和硬边界管理

已授权的有据非物理编译、链接、接口、包装修复由执行作者在同一问题和可靠剩余累计预算内继续，不为每个错误另开合同或咨询科学方法。记录原因、差异、失败/成本和受影响范围；更改实际科学身份时重冻并由原审查员增量复审。

失败次数是诊断信号。优先任务已获用户放宽时，不再仅按次数硬停；新默认合同不无理由添加一两次编译修复死限。盲目重复、没有可定位原因/信息价值、真实硬资源不足或无法确认余额时仍停相应操作。模型/种子/样本/几何/物理时间/目标分母、共享访问和硬预算不能通过工程修复名义改变。用户明确硬次数或既有冻结停止线在被明确修订前继续有效，不追溯洗掉旧违规。

## 四种时钟分别记录

| 类型 | 起点与计量 | 用途 |
|---|---|---|
| execution_wall_hard | 真实受控程序启动到进程树结束/观测；记录所有失败/修复区间，同阶段并发区间按时间并集 | 新合同的程序执行硬超时；程序仍运行的I/O或等待照常计入 |
| continuous_wall_hard | 原合同明定的真实起点至当前时刻/截止，包括其定义内的间隙 | 连续native控制或既有硬时钟；不擅自改成执行累计 |
| milestone_soft | 真实准备/冻结/送审起点及评估节点 | 评估成本、信息价值和wrapper-only状态；不是自动终止或预算重置 |
| coordination_wait | 有真实依据、且没有受控程序运行的模型/交接/审查/用户等待区间 | 解释端到端延迟和角色负担；不是CPU或科学物理时间 |

新合同写明哪种时钟限制什么。程序硬超时不默认包住整个模型推理、审查和人工审批过程；整体交付期限另列里程碑或用户明确的连续硬限制。物理时间/事件时钟与这些执行时间严格区分。

既有连续硬时钟保持原定义、起点、截止和到期记录。当前用户批准新的计时分工后，由原合同负责人登记前瞻修订及适用范围；不把旧间隙事后删除、不重置CPU/失败、不把expired改为合规。运行中的硬限制未正式修订前仍执行，健康任务不重启。

clock_report.py 只解释显式记录，不控制或追加资源：

    python clock_report.py --ledger clock-ledger.json --output clock-summary.json

输入 observed_at 必须有时区。clocks 每项 name/kind/limit_s；连续或软时钟用 origin/origin_source_ref，执行或协调用 intervals（start/end/source_ref）。运行区间 end=null 使用 observed_at；end不得越过观测时间。只有 intervals_complete=true 且 completeness_source_ref 有依据，才计算执行时钟确定余额；部分记录保留unknown并给已知区间下限。不能由沉默、mtime或没有日志推零耗时/已结束。

协调等待不得与声明的运行程序区间重叠，不从活进程的墙钟中扣除等待。milestone_soft 到点仅返回需评估；continuous_wall_hard 过期照常记录hard_limit_reached。返回 automatic_stop_or_extension=false、new_budget_or_window_granted=false；真正控制仍由原受控入口执行。

## 从规则到实际采用

迁移核对四项：现行角色政策和授权；实际派工及接收消息；对应角色能运行的工具/写入边界/状态提交入口；后续一份真实接收结果和实际缺项路由。仅更新SKILL、追加职责说明或创建支持代理不足以证明采用。遗留脚本及严格合同逐项登记差异，保留科学不变量，替换导致常规工作回流的实际入口。
