# HANDOFF.md

> 交接记录 — 给下一个 Agent 的最重要文件

## 当前阶段

**第一阶段：只读扫描、分析、方案设计**

用户明确确认前：
- 不写业务代码
- 不修改游戏客户端
- 不修改参考项目
- 不修改单机 mod 源项目
- 只允许在工作区写文档、流程文件、AGENTS.md

## 最后 commit

(待提交 — 本轮 commit)

## 已完成

1. **TASK-000**: 初始化工作区与 AGENTS.md
   - 创建 `AGENTS.md`
   - 创建 `.gitignore`
   - 初始化 git 仓库

2. **TASK-001**: Offline2.3.1.2 只读扫描与分析
   - 完成 `docs/analysis/01-offline2312-project-scan.md`
   - 确认 Python 2.7
   - 确认 x64 架构
   - 分析核心模块（fake_server, battle, mechanics, drive, shooting）
   - 初步分析单实例限制（Python 层无）

3. **TASK-002**: wot-offline-battles 参考项目扫描
   - 完成 `docs/analysis/02-reference-wot-offline-battles-scan.md`
   - 分析架构（权威 worker + 薄客户端）
   - 分析协议（JSON lines v5, TCP, 30Hz tick）
   - 分析多实例方案（native C + WGC cleanup thunk）
   - 分析预测模型（本地物理 + 确认样本插值）

4. **TASK-003**: 版本差异分析
   - 完成 `docs/analysis/03-version-diff-0.9.22-vs-2.3.1.2.md`
   - 确认关键差异：32-bit → 64-bit
   - 确认 WGC 变化（三个 DLL）
   - 确认 API 变化（载具机制系统）

5. **TASK-004**: 目标架构设计与迁移计划
   - 完成 `docs/analysis/04-target-architecture.md`
   - 完成 `docs/analysis/05-migration-and-sdk-plan.md`
   - 设计目录结构
   - 设计模块划分
   - 制定迁移策略

6. **TASK-005**: 多实例限制专项分析
   - 初步分析完成
   - 确认 Python 层无单实例限制
   - 确认需要 native C x64 重写
   - 标记为最高优先级风险

7. **TASK-006**: 任务拆解与风险文档
   - 完成 `docs/analysis/06-task-breakdown.md`
   - 完成 `docs/analysis/07-risks-and-open-questions.md`
   - 拆解 10 个里程碑（M0-M9）
   - 识别主要风险和开放问题

## 未完成

1. **等待用户确认**：第一阶段完成后，等待用户确认才能进入编码阶段
2. **多实例逆向分析**：需要专门的逆向任务（M0.1）
3. **2.3.1.2 WGC 结构分析**：需要逆向 wgc_api.dll

## 正在处理

- 第一阶段文档撰写完成
- 等待用户确认

## 下一步建议

1. **等待用户确认**：向用户汇报第一阶段成果，等待确认
2. **用户确认后**：进入编码阶段，按里程碑推进
3. **优先解决多实例**：M0 是最高优先级，阻塞联机测试
4. **并行进行**：M0 的逆向分析可与其他任务并行

## 关键文件

### 分析文档

- `docs/analysis/01-offline2312-project-scan.md` — Offline2.3.1.2 扫描报告
- `docs/analysis/02-reference-wot-offline-battles-scan.md` — 参考项目扫描报告
- `docs/analysis/03-version-diff-0.9.22-vs-2.3.1.2.md` — 版本差异分析
- `docs/analysis/04-target-architecture.md` — 目标架构设计
- `docs/analysis/05-migration-and-sdk-plan.md` — 迁移与 SDK 计划
- `docs/analysis/06-task-breakdown.md` — 任务拆解
- `docs/analysis/07-risks-and-open-questions.md` — 风险与开放问题

### 流程文档

- `AGENTS.md` — Agent 入口文件
- `docs/agent/PROGRESS.md` — 项目进展记录
- `docs/agent/HANDOFF.md` — 交接记录（本文件）
- `docs/agent/DECISIONS.md` — 决策记录
- `docs/agent/OPEN_QUESTIONS.md` — 开放问题

### 源项目（只读）

- `D:\Projects\Offline2.3.1.2` — 单机 mod 源
- `D:\Projects\wot-offline-battles` — 参考项目
- `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2` — 游戏安装目录

## 关键发现

### Offline2.3.1.2

1. **Python 2.7**：bytecode magic `62211`
2. **x64 架构**：`WorldOfTanks(x64) 2.3.1.10157`
3. **51 个 .py 文件**：反编译质量良好
4. **核心模块**：
   - `fake_server.py` (208 KB) — 假服务器
   - `battle.py` (165 KB) — 战斗生命周期
   - `mechanics.py` (243 KB) — 载具机制
   - `drive.py` (206 KB) — 驾驶模拟
   - `shooting.py` (179 KB) — 射击机制
5. **单机模式**：通过 `BigWorld.connect("")` + FakeCell 拦截
6. **无单实例限制**：Python 层无 OS 级互斥

### 参考项目

1. **架构**：权威 worker + 薄客户端
2. **协议**：JSON lines v5, TCP, 30Hz tick, 15Hz 快照
3. **多实例**：native C + WGC cleanup thunk + `wot_client_mutex`
4. **预测**：本地物理 + 确认样本插值
5. **部署**：.wotmod + sidecar pyd

### 版本差异

1. **架构**：32-bit → 64-bit（最大差异）
2. **Python**：都是 2.7，基本兼容
3. **WGC**：三个 DLL，结构可能不同
4. **API**：大量新 API（载具机制系统）

### 多实例限制

1. **Python 层无**：Offline2.3.1.2 无 OS 级单实例限制
2. **引擎层有**：BigWorld/WGC 可能有单实例检查
3. **参考方案**：native C + WGC cleanup thunk
4. **必须重写**：0.9.22 的 32-bit 方案无法用于 2.3.1.2

## 风险

### 高风险

1. **x64 native 实例守卫重写** — 必须解决才能进行联机测试
2. **2.3.1.2 WGC 结构未知** — 需要逆向分析

### 中风险

3. **BigWorld API 变化** — 参考项目代码无法直接使用
4. **机制系统复杂度** — 工作量大
5. **Python 2.7 限制** — 客户端开发受限

## 待用户确认

1. **多实例方案选择** — 阻塞进入编码阶段
2. 客户端部署方式 — 不阻塞
3. Bot AI 范围 — 不阻塞
4. 单人模式处理 — 不阻塞

## 禁止事项提醒

- 禁止修改 `D:\Projects\Offline2.3.1.2`
- 禁止修改 `D:\Projects\wot-offline-battles`
- 禁止修改游戏安装目录、exe、dll、核心资源
- 禁止用户确认前写业务代码
- 禁止无证据编造 API、文件、协议
- 禁止把大量代码写进单文件
- 禁止跳过测试和文档
- 禁止重复造轮子，能用 Python 库就用 Python 库
