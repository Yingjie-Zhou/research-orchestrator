# Research Orchestrator · 科研工作流主控

一个用于持续科研、数值模拟与模型验证的 Codex skill。围绕可验证的科学终点组织并行研发、完整成果交付和独立审查，让项目在已有授权与资源范围内持续推进。

当前版本包含 2026-10-06 的 V6 流程更新：

- **完整工作单元**：把实施、必要依赖、自检、允许的有限验证、同问题修复和可用交付放进同一个任务。
- **具名接续**：明确下一动作的条件和原范围，作者在已有授权、累计预算与操作限制内连续执行。
- **直接交付**：成果交给实际消费者与原独立审查员，普通反馈回原作者，主控接收里程碑和真实升级事项。

同时保留目标导向的并行派工、局部阻塞隔离、难点顾问咨询、独立科学审查，以及失败、未知量和累计成本记录。模型与角色配置遵从用户及项目的现行选择。

## 安装

将仓库中的 [research-orchestrator](research-orchestrator) 文件夹复制到你的 Codex skills 目录。默认位置是 `~/.codex/skills/`；已设置 `CODEX_HOME` 时使用其 `skills` 子目录。

Windows PowerShell：

```powershell
git clone https://github.com/Yingjie-Zhou/research-orchestrator.git
$skillDir = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
Copy-Item -LiteralPath '.\research-orchestrator\research-orchestrator' -Destination $skillDir -Recurse
```

Linux / macOS：

```sh
git clone https://github.com/Yingjie-Zhou/research-orchestrator.git
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R research-orchestrator/research-orchestrator "${CODEX_HOME:-$HOME/.codex}/skills/"
```

安装前检查是否已有同名 skill；更新时保留自己的本地修改。

## 使用

在 Codex 中提出项目目标，例如：

> 使用 $research-orchestrator 继续这个科研项目。先读取已有状态与证据，明确最终目标，安排可独立推进的研发任务；让作者完成完整问题并直接交付，保留独立审查、原科学范围和累计成本。

入口是 [SKILL.md](research-orchestrator/SKILL.md)。参考文件按需读取；已有项目可以继续使用原有状态格式。JSON 模板和文件工具用于需要重复整理、接收或状态比较的项目。

## 内容

| 目录 | 用途 |
|---|---|
| `research-orchestrator/SKILL.md` | 科学终点、任务组织、持续推进与验收规则 |
| `research-orchestrator/references/` | 角色分工、约束尺度、协调适配、稳定接收、连续工作单元和案例 |
| `research-orchestrator/assets/` | 任务、结果、状态、接收、时钟与接续计划模板 |
| `research-orchestrator/scripts/` | Python 标准库文件助手 |
| `research-orchestrator/tests/` | 文件助手的回归测试 |

文件助手要求 Python 3.8+。它们生成简报和投递参数、核对产物、准备状态更新、整理时间区间；实际派工及消息发送使用当前环境已授权的工具。科学接受依据实际证据和独立审查，项目完成依据用户要求的终点。

运行测试：

```sh
python -B -m unittest discover -s research-orchestrator/tests
```

## 适用范围

适合多阶段科研、数值模拟、模型验证及已有研究的持续接续。单次计算、普通代码修改或仅阅读评价通常直接完成，不需要启动完整调度流程。

该工作流来自 MRPC 科研项目中的实际迭代。案例帮助解释分工与科学边界，具体模型、预算、轮次和门限需要按新项目决定。目前观察支持部分协作机制改善；整体提速、成本下降和物理结论仍须分别验证。
