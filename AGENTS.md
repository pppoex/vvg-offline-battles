# AGENTS.md

本文件是 `vvg-offline-battles` 项目的 Agent 入口文件。所有后续 AI Agent 必须先读本文件。

## 1. 项目使命

将坦克世界 2.3.1.2 离线 mod 改造成服务器权威的联机架构：

- `sim-worker` 作为权威服务器。
- 所有玩家是薄客户端。
- 薄客户端只负责输入、渲染、UI、预测。
- 服务器权威决定移动、炮塔、开火、命中、伤害、死亡。
- 不保留单机模式。
- 单人运行时也连接本地 `sim-worker`。
- 支持断线重连。
- 必须 Windows 运行。
- 先做命令行启动器，不做 GUI。
- 必须解除游戏单实例限制，允许多开。

## 2. 当前阶段

**编码阶段：M0 已完成，下一个里程碑 M1**

已完成：
- 第一阶段只读分析（7 篇文档）
- M0 多实例限制解除（双开验证通过）

当前状态：
- 可以写业务代码
- 按里程碑推进（M1-M9）
- 每个里程碑完成后运行测试、更新文档、提交 commit

禁止：
- 不修改游戏客户端本体（exe/dll/pkg）
- 不修改参考项目
- 不修改单机 mod 源项目
- 部署只能通过工作区项目内脚本完成

## 3. 关键路径

| 路径 | 说明 | 访问权限 |
|---|---|---|
| `D:\Projects\Offline2.3.1.2` | 单机 mod 源（反编译 py） | **只读** |
| `D:\Projects\wot-offline-battles` | 参考项目（0.9.22 联机） | **只读参考** |
| `D:\Projects\vvg-offline-battles` | 工作区（唯一可写） | **可读写** |
| `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2` | 游戏安装目录（经符号链接） | **只读** |
| `D:\Python27` | Python 2.7 运行时（经符号链接） | **只读** |

## 4. 硬性约束

- 单机 mod 源：`D:\Projects\Offline2.3.1.2`，只读。
- 参考项目：`D:\Projects\wot-offline-battles`，只读参考。
- 工作区：`D:\Projects\vvg-offline-battles`，唯一允许修改。
- 部署只能通过工作区项目内脚本/启动器完成。
- 不做反作弊/安全校验，但保持服务器权威。
- 代码必须模块化，禁止大量逻辑塞进一个文件。
- 必须测试，必须文档。
- 禁止重复造轮子，能用 Python 库就用 Python 库。
- 多实例限制是最高优先级问题，编码前必须解决。

## 5. 每轮工作循环

### 每轮开始

1. 读 `AGENTS.md`。
2. 读 `docs/agent/HANDOFF.md`。
3. 读 `docs/agent/PROGRESS.md`。
4. 读 `docs/agent/MILESTONES.md`（里程碑进度）。
5. 读 `docs/agent/OPEN_QUESTIONS.md`。
6. 执行 `git status --short`。

### 每轮结束

1. 更新 `docs/agent/PROGRESS.md`。
2. 更新 `docs/agent/HANDOFF.md`。
3. 更新 `docs/agent/MILESTONES.md`（如涉及里程碑）。
4. 必要时更新 `docs/agent/DECISIONS.md`。
5. 必要时更新 `docs/agent/OPEN_QUESTIONS.md`。
6. 运行测试或验证命令；不能运行则写原因。
7. `git status --short`。
8. `git add` 本轮相关文件。
9. `git commit`。
10. 回复中报告 commit hash、message、文件、交接路径。

## 6. Commit 规范

格式：

```text
<type>(<scope>): <中文摘要> [<task-id>]
```

第一阶段常用：

```text
chore(repo): 初始化工作区与 AGENTS.md [TASK-000]
docs(analysis): 完成 Offline2.3.1.2 只读扫描 [TASK-001]
docs(agent): 更新阶段一交接记录 [TASK-001]
```

## 7. 必读文件顺序

1. `AGENTS.md`
2. `docs/agent/HANDOFF.md`
3. `docs/agent/PROGRESS.md`
4. `docs/agent/MILESTONES.md`
5. `docs/agent/OPEN_QUESTIONS.md`
6. `docs/agent/DECISIONS.md`
7. `docs/analysis/*.md`

## 8. 目录约定

目标结构（编码阶段）：

```text
AGENTS.md
docs/
  analysis/
  agent/
src/
  sdk/
  sim_worker/
  client/
  protocol/
  launcher/
  deploy/
  multiclient/
tests/
tools/
```

第一阶段只允许创建 `AGENTS.md`、`docs/analysis/`、`docs/agent/` 和必要 `.gitignore`。

## 9. 交接模板

每次更新 `docs/agent/HANDOFF.md`：

```md
# 当前交接摘要

## 当前阶段
## 最后 commit
## 已完成
## 未完成
## 正在处理
## 下一步建议
## 关键文件
## 关键发现
## 风险
## 待用户确认
## 禁止事项提醒
```

## 10. 禁止事项

- 禁止修改 `D:\Projects\Offline2.3.1.2`。
- 禁止修改 `D:\Projects\wot-offline-battles`。
- 禁止修改游戏安装目录、exe、dll、核心资源。
- 禁止用户确认前写业务代码。
- 禁止无证据编造 API、文件、协议。
- 禁止把大量代码写进单文件。
- 禁止跳过测试和文档。
- 禁止重复造轮子，能用 Python 库就用 Python 库。

## 11. 多实例限制专项提醒

游戏客户端不允许同时运行多个实例。联机测试和实际运行都需要多个客户端进程同时连接 sim-worker。

**这是进入编码阶段前必须解决的第一问题。**

0.9.22 参考项目的方案：native C 模块释放 WGC guard 和 `wot_client_mutex`，通过环境变量 `OFFLINE_LAN_0922_ALLOW_MULTIPLE_CLIENTS=1` 启用。

2.3.1.2 是 **x64** 客户端，0.9.22 的 32-bit RVA 方案无法直接使用，需要重新实现。

详见 `docs/analysis/01-offline2312-project-scan.md` 和 `docs/analysis/07-risks-and-open-questions.md`。

## 12. 关键技术事实

- **Python 版本**：两个项目均为 Python 2.7。
- **客户端架构**：0.9.22 是 32-bit x86；2.3.1.2 是 **64-bit x64**。
- **游戏版本**：2.3.1.2 #921，EU realm，branch v2.3.1。
- **引擎**：BigWorld（2.3.1.2 版本使用 python27.dll 在 win64/ 下）。
- **WGC**：2.3.1.2 使用 Wargaming Game Center（wgc_api.dll 等）。
- **协议参考**：JSON over TCP，newline-delimited，PROTOCOL_VERSION=5。
- **Tick rate**：参考项目 30 Hz 服务器，15 Hz 快照。
