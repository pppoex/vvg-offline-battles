# PROGRESS.md

> 项目进展记录

| 轮次 | 任务ID | 目标 | 状态 | 修改文件 | 验证方式 | commit | 时间 |
|---|---|---|---|---|---|---|---|
| 1 | TASK-000 | 初始化工作区与 AGENTS.md | 已完成 | AGENTS.md, .gitignore | 文件存在检查 | 3528633 | 2026-09-12 |
| 1 | TASK-001 | Offline2.3.1.2 只读扫描与分析 | 已完成 | docs/analysis/01-offline2312-project-scan.md | 文档评审 | 3528633 | 2026-09-12 |
| 1 | TASK-002 | wot-offline-battles 参考项目扫描 | 已完成 | docs/analysis/02-reference-wot-offline-battles-scan.md | 文档评审 | 3528633 | 2026-09-12 |
| 1 | TASK-003 | 版本差异分析 0.9.22 vs 2.3.1.2 | 已完成 | docs/analysis/03-version-diff-0.9.22-vs-2.3.1.2.md | 文档评审 | 3528633 | 2026-09-12 |
| 1 | TASK-004 | 目标架构设计与迁移计划 | 已完成 | docs/analysis/04-target-architecture.md, 05-migration-and-sdk-plan.md | 文档评审 | 3528633 | 2026-09-12 |
| 1 | TASK-005 | 多实例限制专项分析 | 已完成 | docs/analysis/01, 07 | 文档评审 | 3528633 | 2026-09-12 |
| 1 | TASK-006 | 任务拆解与风险文档 | 已完成 | docs/analysis/06, 07 | 文档评审 | 3528633 | 2026-09-12 |
| 1 | TASK-007 | 流程文档与提交 | 已完成 | docs/agent/*.md | 文件存在检查 | 3528633 | 2026-09-12 |
| 2 | TASK-M0 | 多实例解除 x64 逆向+实现 | 已完成 | src/multiclient/**, docs/analysis/multiclient-research.md | 编译 + 13 单测 | f59c7ca | 2026-09-12 |
| 3 | TASK-M0.1 | 游戏 mod 集成 + 部署 + starter | 已完成 | src/client/**, src/deploy/install_multiclient.py | 编译 + 22 单测 + 部署 | 3e9e969 | 2026-09-12 |
| 4 | TASK-M0.2 | res_mods 只加载 .pyc：Py2.7 编译 | 已完成 | src/deploy/install_multiclient.py | 23 单测 + magic=62211 | 19b6ff6 | 2026-09-12 |
| 5 | TASK-M0.3 | 无 _ctypes → 扩展导入修复 | 已完成 | src/multiclient/instance_guard.py, native/instance_guard.c | 27 单测 + 真机双开通过 | 78a989a | 2026-09-12 |
| 6 | TASK-M0.F | M0 完成：双开验证通过，推送到 GitHub | 已完成 | docs/agent/*.md | 用户确认双开正常 | 7c81824 | 2026-09-12 |
| 7 | TASK-M1 | 项目骨架与 SDK 抽取 | 已完成 | pyproject.toml, src/sdk/**, tests/unit/test_sdk_*.py | pytest 全绿 + Py2.7 编译 | a391fba | 2026-09-12 |
| 8 | TASK-M2 | 协议与序列化 | 已完成 | src/protocol/**, tests/unit/test_protocol.py, test_serializer.py, docs/design/protocol.md | pytest 全绿 + Py2.7 编译 | 2ae17fe | 2026-09-12 |
| 9 | TASK-M3 | sim-worker 权威服务器骨架 | 已完成 | src/sim_worker/**, tests/integration/test_server.py, docs/design/sim_worker.md | pytest 全绿（unit+integration） | de5dd79 | 2026-09-12 |
| 10 | TASK-M4 | 薄客户端补丁 | 已完成 | src/client/vvg_client/**, mod_vvg_client.py, install_*.py, offline_entry, worker_starter, sim_worker 日志 | pytest 全绿 + 真机进车库 + player/worker join | b89dbf9…09aac72 | 2026-09-12 |
| 11 | TASK-M5 | 命令行启动器与统一部署 | 已完成（代码+测试；真机一键待验） | src/launcher/**, src/deploy/install_all.py, tests/integration/test_launcher.py, docs/design/launcher.md | pytest 全绿 + CLI dry-run 冒烟 | 8e4f0da | 2026-09-13 |
| 11b | TASK-M5.b | 构建产物统一 build/ + launcher build | 已完成 | build/multiclient/native/**, src/launcher/build.py, install_multiclient, build.ps1 | pytest 全绿 + 产物迁移验证 | 6ff7ad5 | 2026-09-13 |
| 11c | TASK-M5.c | build 补 py→pyc（2.7 magic=62211） | 已完成 | src/launcher/bytecode.py, build.py, cli.py | pytest 全绿 + protocol/constants.pyc magic 校验 | f08dceb | 2026-09-13 |
| 12 | TASK-M6-DESIGN | M6 联机架构与用户确认 | 已完成（设计） | docs/design/m6_architecture.md, DECISIONS, OPEN_QUESTIONS, HANDOFF | 用户多轮确认 + 文档评审 | 5c7dec1 | 2026-09-14 |
| 13 | TASK-M6.P2 | M6 Phase2 join 拦截 + 本机 Web 状态页 | 已完成 | join_gate, webui/server, ui/join_flow, bootstrap, test_m6_join_web | pytest 全绿 + Py2.7 编译 | 9ac649c | 2026-09-14 |
| 14 | TASK-M6.P3 | worker_pose 中继 + 原地 Bot + catalog_hash | 已完成 | protocol, sim_worker room/session/server, worker_authority, tests | pytest 全绿 + Py2.7 编译 | eeb68e7 | 2026-09-14 |
| 15 | TASK-M6.P4 | RemoteScene + leave 回车库 + Web /leave | 已完成 | presentation/remote_scene, session, webui, join_flow, tests | pytest 全绿 + Py2.7 编译 | ce8f4e3 | 2026-09-14 |

## 状态说明

- **进行中**：任务正在执行
- **已完成**：任务已完成并通过验证
- **阻塞**：任务被阻塞，等待解决
- **待确认**：任务等待用户确认

## 里程碑状态

| 里程碑 | 状态 | 说明 |
|---|---|---|
| M0: 多实例限制解除 | ✅ **已完成** | 双开验证通过 |
| M1: 项目骨架与 SDK | ✅ **已完成** | SDK 抽取 + 数学库 + 单测框架 |
| M2: 协议与序列化 | ✅ **已完成** | protocol 包 + 能力协商 + 单测 + 文档 |
| M3: sim-worker 服务器 | ✅ **已完成（骨架）** | TCP 握手 + 房间 + 30Hz tick + 15Hz 快照 |
| M4: 薄客户端补丁 | ✅ **已完成 + 真机通过** | 进车库 + handshake + sim-worker join |
| M5: 启动器与部署 | ✅ **代码完成 + 已推送** | build/deploy/server/player/worker；产物在 build/；真机一键待用户验证 |
| M6: 基础同步 | ⬜ 未开始 | — |
| M7: 战斗同步 | ⬜ 未开始 | — |
| M8: 断线重连 | ⬜ 未开始 | — |
| M9: 测试与文档 | ⬜ 未开始 | — |
