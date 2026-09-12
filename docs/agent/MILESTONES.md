# MILESTONES.md — 里程碑总览与进度追踪

> 最后更新：2026-09-12（M3 完成后）
> 用途：追踪所有里程碑的进度、交付物、验收标准和未来方向

---

## 总体进度

```
M0 ████████████████████████████████ 100%  ✅ 已完成
M1 ████████████████████████████████ 100%  ✅ 已完成
M2 ████████████████████████████████ 100%  ✅ 已完成
M3 ████████████████████████████████ 100%  ✅ 已完成
M4 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%  ⬜ 未开始
M5 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%  ⬜ 未开始
M6 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%  ⬜ 未开始
M7 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%  ⬜ 未开始
M8 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%  ⬜ 未开始
M9 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%  ⬜ 未开始

整体进度: 40% (4/10 里程碑)
```

---

## M0: 多实例限制解除 ✅

**状态**: 已完成并验证  
**完成时间**: 2026-09-12  
**Commits**: `f59c7ca`, `3e9e969`, `19b6ff6`, `78a989a`, `7c81824`

### 目标

让同一台机器可以运行多个游戏客户端实例，用于联机和本地测试。

### 交付物

| 文件 | 说明 |
|---|---|
| `src/multiclient/native/instance_guard.c` | x64 实例守卫（PE 校验 + 句柄枚举释放） |
| `src/multiclient/native/worker_starter.c` | worker 启动器 |
| `src/multiclient/native/build.ps1` | MSVC 编译脚本 |
| `src/multiclient/instance_guard.py` | Python 接口 |
| `src/client/mod_vvg_instance_guard.py` | BigWorld mod 入口 |
| `src/client/vvg_instance_guard/bootstrap.py` | mod 初始化 |
| `src/deploy/install_multiclient.py` | 部署脚本（含 .pyc 编译） |
| `docs/analysis/multiclient-research.md` | 逆向分析报告 |
| `docs/analysis/multiclient-debug-log.md` | 调试日志 |

### 验收标准

- ✅ 两个客户端可同时启动并进入登录/战斗
- ✅ 进程、窗口、互斥体检查通过
- ✅ 用户确认双开正常

### 关键技术发现

1. **主互斥体**: `WOT_STARTUP_MUTEX`（非 0.9.22 的 `wot_client_mutex`）
2. **Python C API**: 通过 `python27.dll` 的 `GetProcAddress` 解析
3. **游戏只加载 .pyc**: magic = `03 f3 0d 0a` (62211)
4. **内嵌 Python 无 `_ctypes`**: 必须用 `imp.load_dynamic`
5. **日志位置**: `vvg-*-python.log`（非 `python.log`）

### 使用方式

```powershell
# 启动第一个客户端
cd "D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\win64"
.\vvg_worker_starter.exe --player

# 等第一个进入车库后，启动第二个
.\vvg_worker_starter.exe --player
```

---

## M1: 项目骨架与 SDK 抽取 ✅

**状态**: 已完成  
**完成时间**: 2026-09-12  
**Commits**: 见 PROGRESS.md TASK-M1

### 目标

建立项目骨架，从 Offline2.3.1.2 抽取可复用 SDK。

### 交付物

| 文件 | 说明 |
|---|---|
| `pyproject.toml` | 项目配置 + pytest pythonpath |
| `src/sdk/__init__.py` | SDK 包入口（2/3 兼容） |
| `src/sdk/hooks.py` | Hook 系统（抽取 + 修 Decompyle artifact） |
| `src/sdk/log.py` | 日志系统（抽取 + 修 artifact） |
| `src/sdk/config.py` | 配置（去掉 OFFLINE_*，联机默认值） |
| `src/sdk/math/vector.py` | Vector3（替代 BigWorld Math.Vector3） |
| `src/sdk/math/matrix.py` | Matrix 4x4（替代 BigWorld Math.Matrix） |
| `tests/unit/test_sdk_*.py` | SDK 单元测试 |

### 验收标准

- ✅ 项目骨架建立完成
- ✅ SDK 基础模块可用
- ✅ 单元测试框架运行
- ✅ `pytest tests/unit/` 通过
- ✅ SDK 全部文件 Python 2.7 可编译

### 测试方式

```bash
python -m pytest tests/unit/
```

### 关键决策

1. SDK 必须 **Python 2/3 双兼容**（客户端 2.7，服务器/测试 3.x）
2. `config.py` 不再携带 Offline 单机假服务器配置；只保留网络/会话默认值
3. 数学库对齐 BigWorld 用法：`translation`、`yaw/pitch/roll`、`applyPoint/applyVector`
4. 欧拉角约定：R = Ry·Rx·Rz；yaw 绕 Y，pitch 向上抬为负，roll 绕 Z

### 风险

- Offline2.3.1.2 代码质量（Decompile++ artifact）— 已在抽取时清理
- 宿主 Python 3.14 无法 `imp.load_dynamic` 加载 Py2.7 pyd — M0 测试已改为可跳过

### 未来方向

SDK 是后续所有模块的基础：
- M2 协议层依赖 `config` 默认端口 / PROTOCOL_VERSION
- M3 sim-worker 使用 `sdk.math` 做权威模拟
- M4 客户端预测使用同一套 Vector3/Matrix

---

## M2: 协议与序列化 ✅

**状态**: 已完成  
**完成时间**: 2026-09-12  
**依赖**: M1

### 目标

定义客户端-服务器-Worker 之间的消息协议。

### 交付物

| 文件 | 说明 |
|---|---|
| `src/protocol/__init__.py` | 包入口（2/3 兼容） |
| `src/protocol/constants.py` | PROTOCOL_VERSION=5、消息类型、限制、端口 28782 |
| `src/protocol/messages.py` | hello/welcome/input 等 builder + 校验 |
| `src/protocol/serializer.py` | JSON lines + LineDecoder |
| `src/protocol/capabilities.py` | 能力名与 negotiate() |
| `tests/unit/test_protocol.py` | 消息与协商单测 |
| `tests/unit/test_serializer.py` | 序列化专项单测 |
| `docs/design/protocol.md` | 协议文档 |

### Commits

- `2ae17fe` feat(protocol): 实现 JSON lines 协议层与能力协商 [TASK-M2]
- `59cf674` docs(agent): M2 收尾回填 commit hash [TASK-M2]

### 验收标准

- ✅ 协议定义完整
- ✅ 序列化/反序列化正确
- ✅ 能力协商可用
- ✅ 单元测试通过
- ✅ 与 sdk.config 端口/版本对齐
- ✅ Python 2.7 可编译

### 测试方式

```bash
pytest tests/unit/test_protocol.py tests/unit/test_serializer.py
```

### 关键决策

1. 对齐 0.9.22 v5：JSON lines、hello 首条、ping/pong、状态屏障
2. 必选能力 `core_session_v1`；movement/fire/reconnect 预留名
3. 单条消息 256 KiB；紧凑 JSON + ensure_ascii
4. protocol 包 2/3 双兼容（客户端与服务器共用）

### 风险

- snapshot.payload schema 在 M6 前保持宽松，避免过早锁死

### 未来方向

M3 sim-worker 使用本协议完成握手与 roster；M4 客户端复用 LineDecoder。

---

## M3: sim-worker 权威服务器 ✅

**状态**: 已完成（骨架）  
**完成时间**: 2026-09-12  
**依赖**: M2

### 目标

实现权威服务器骨架，运行 30 Hz 世界 tick。

### 交付物

1. `src/sim_worker/` — 服务器模块
   - `main.py` — 入口
   - `server.py` — TCP 服务器
   - `session.py` — 会话
   - `tick.py` — 世界 tick 循环
   - `room/lobby.py` / `room/room.py` — 房间管理
2. `tests/integration/test_server.py` — 集成测试
3. `docs/design/sim_worker.md` — 设计文档

### Commits

- `feat(sim_worker): 实现 TCP 服务器骨架与 30Hz tick [TASK-M3]`（本轮业务 commit）

### 验收标准

- ✅ 服务器可启动
- ✅ 30 Hz tick 循环稳定（TickLoop + 手动 run_ticks 验证）
- ✅ 房间管理可用（join/leave/选队/换车/roster）
- ✅ 快照广播正常（battle 相位 15 Hz）
- ✅ hello/welcome/能力协商与 protocol.md 对齐

### 测试方式

```bash
pytest tests/integration/test_server.py
# 或全量
pytest tests/unit tests/integration
```

### 关键决策

1. 复用 `src/protocol` builder，不另起协议
2. 线程模型：TCP handler 线程 + 独立 Tick 线程 + 全局 RLock
3. M3 input 仅写会话姿态占位；权威积分 M6 接入 sdk.math
4. leave_battle 暂为整房回 waiting

### 风险

- 后续 M6 迁移 Offline drive.py 时替换占位积分

### 未来方向

- M4 薄客户端接入同一协议
- M5 启动器拉起 sim-worker（单人也启）
- M6 基础同步

---

## M4: 薄客户端补丁 ⬜

**状态**: 未开始  
**预计时间**: 3-4 天  
**依赖**: M2

### 目标

实现薄客户端，连接服务器，接收快照，发送输入。

### 交付物

1. `src/client/` — 客户端模块
   - `mod_entry.py` — BigWorld mod 入口
   - `bootstrap.py` — 初始化
   - `session.py` — 会话管理
   - `network/` — 网络层
   - `prediction/` — 客户端预测
   - `render/` — 渲染呈现
   - `ui/` — UI 补丁
   - `hooks/` — BigWorld hook

### 验收标准

- ✅ 客户端可连接服务器
- ✅ 预测和插值正常
- ✅ BigWorld hook 可用
- ✅ mod 可加载

### 测试方式

```bash
pytest tests/integration/test_client.py
```

### 风险

- BigWorld API 变化
- Python 2.7 限制
- 预测精度

### 未来方向

客户端需要与 Offline2.3.1.2 的 UI 和 hook 系统集成。

---

## M5: 命令行启动器与部署 ⬜

**状态**: 未开始  
**预计时间**: 2-3 天  
**依赖**: M3, M4

### 目标

实现命令行启动器，自动化部署到 res_mods。

### 交付物

1. `src/launcher/` — 启动器模块
2. `src/deploy/` — 部署脚本（已部分存在于 M0）
3. `docs/design/launcher.md` — 使用文档

### 验收标准

- ✅ 部署脚本可用
- ✅ 启动器可用
- ✅ 文档完整

### 测试方式

```bash
pytest tests/integration/test_launcher.py
```

### 风险

- pyc magic number 兼容性
- 部署路径问题

### 未来方向

启动器是用户入口，需要确保：
- 易用性
- 错误处理
- 文档完整

---

## M6: 基础同步 ⬜

**状态**: 未开始  
**预计时间**: 3-4 天  
**依赖**: M3, M4

### 目标

实现基础同步：进入战斗、移动、炮塔。

### 交付物

1. 战斗进入流程
2. 移动同步
3. 炮塔同步

### 验收标准

- ✅ 两个客户端可进入同一场战斗
- ✅ 移动同步正常
- ✅ 炮塔同步正常

### 测试方式

```bash
pytest tests/integration/test_battle_enter.py test_movement_sync.py test_turret_sync.py
```

### 风险

- 移动物理精度
- 网络延迟影响

### 未来方向

基础同步是战斗同步的基础，需要确保：
- 同步精度
- 延迟补偿
- 平滑插值

---

## M7: 战斗同步 ⬜

**状态**: 未开始  
**预计时间**: 5-7 天  
**依赖**: M6

### 目标

实现战斗同步：开火、命中、伤害、死亡。

### 交付物

1. 开火同步
2. 命中同步
3. 伤害同步
4. 死亡同步

### 验收标准

- ✅ 开火同步正常
- ✅ 命中同步正常
- ✅ 伤害同步正常
- ✅ 死亡同步正常

### 测试方式

```bash
pytest tests/integration/test_shooting.py test_hit.py test_damage.py test_death.py
```

### 风险

- 命中判定精度
- 伤害计算复杂度

### 未来方向

战斗同步是联机体验的核心，需要确保：
- 服务器权威
- 客户端预测
- 状态一致性

---

## M8: 断线重连 ⬜

**状态**: 未开始  
**预计时间**: 2-3 天  
**依赖**: M7

### 目标

实现断线重连功能。

### 交付物

1. 断线检测
2. 重连逻辑
3. 状态恢复

### 验收标准

- ✅ 断线可检测
- ✅ 自动重连正常
- ✅ 状态恢复正确

### 测试方式

```bash
pytest tests/integration/test_reconnect.py
```

### 风险

- 状态恢复不完整
- 重连超时处理

### 未来方向

断线重连是联机稳定性的重要保障。

---

## M9: 测试、文档、稳定性收尾 ⬜

**状态**: 未开始  
**预计时间**: 3-4 天  
**依赖**: M1-M8

### 目标

完善测试、文档，确保稳定性。

### 交付物

1. 完整测试覆盖
2. 完整文档
3. 稳定性验证

### 验收标准

- ✅ 测试覆盖完整
- ✅ 文档完整
- ✅ 稳定性验证通过

### 测试方式

```bash
pytest tests/
# 长时间运行测试
```

### 风险

- 测试覆盖率不足
- 文档不完整
- 稳定性问题

### 未来方向

收尾阶段确保项目可交付、可维护。

---

## 里程碑依赖关系

```
M0 (多实例) ✅ ─────────────────────────────────┐
                                                │
M1 (SDK) ✅ ──→ M2 (协议) ✅ ──→ M3 (服务器) ✅ ──→ M6 (基础同步) ⬜ ──→ M7 (战斗同步) ⬜ ──→ M8 (重连) ⬜ ──→ M9 (收尾) ⬜
                │              │                    │
                └──────────────┼────────────────────┘
                               │
M4 (客户端) ⬜ ←────────────────┘
     │
     └──→ M5 (启动器) ⬜
```

**关键路径**: M1 → M2 → M3 → M6 → M7 → M8 → M9

**并行任务**:
- M4（客户端）可与 M3（服务器）并行
- M5（启动器）可与 M6-M8 并行

---

## 最小验收标准（最终项目）

- ✅ 两个客户端能进入同一场战斗
- ⬜ 移动同步
- ⬜ 炮塔同步
- ⬜ 开火同步
- ⬜ 命中同步
- ⬜ 伤害同步
- ⬜ 死亡同步
- ⬜ 服务器权威
- ⬜ 单人也能以联机模式运行
- ⬜ 断线重连可用
- ⬜ 不做反作弊
- ⬜ 有命令行启动器
- ⬜ 代码模块化，多文件拆分
- ⬜ 有测试
- ⬜ 有文档
- ✅ 多实例限制已解除，可同时启动多个客户端

---

## 关键技术约束（所有里程碑必须遵守）

1. **客户端 Python 2.7**: 只能用标准库，不能用现代 Python 特性
2. **游戏只加载 .pyc**: 必须用 Python 2.7 编译
3. **内嵌 Python 无 _ctypes**: 不能用 ctypes，用 imp.load_dynamic
4. **服务器 Python 3**: 可用现代 Python 特性
5. **不做反作弊**: 但保持服务器权威
6. **代码模块化**: 禁止大量代码塞进单文件
7. **必须测试**: 每个里程碑完成后运行测试
8. **必须文档**: 每个里程碑完成后更新文档

---

## 附录：参考项目路径

| 路径 | 说明 |
|---|---|
| `D:\Projects\Offline2.3.1.2` | 单机 mod 源（只读） |
| `D:\Projects\wot-offline-battles` | 参考项目（只读） |
| `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2` | 游戏安装目录（只读，部署除外） |
| `D:\Projects\vvg-offline-battles` | 工作区（可读写） |

## 附录：GitHub 仓库

| 分支 | 用途 | 最后 commit |
|---|---|---|
| `main` | 主分支，后续开发 | `2ae17fe`（TASK-M2） |
| `base` | 存档，不再改动 | `5636a9b` |

仓库地址：https://github.com/pppoex/vvg-offline-battles
