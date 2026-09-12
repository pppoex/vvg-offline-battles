# 05 - 迁移与 SDK 计划

> 计划时间：2026-09-12
> 目标：从 Offline2.3.1.2 抽取 SDK，在工作区实现联机架构

## 1. 迁移策略总览

### 1.1 三种代码处理方式

| 方式 | 说明 | 适用场景 |
|---|---|---|
| **复制** | 直接复制代码，最小修改 | 版本无关的通用代码 |
| **适配** | 复制后修改以适配新版本 | 需要小改动的代码 |
| **重写** | 完全重写 | API 变化大或架构不同的代码 |

### 1.2 迁移优先级

```
1. 协议层（可直接复用参考项目设计）
2. 服务器骨架（可直接复用参考项目架构）
3. SDK（从 Offline2.3.1.2 抽取）
4. 客户端网络层（新写，参考项目）
5. 客户端预测（参考项目 snapshot_sync）
6. 客户端 UI/hook（从 Offline2.3.1.2 适配）
7. 战斗逻辑（从 Offline2.3.1.2 迁移到 sim-worker）
8. 多实例（重写 native C）
```

## 2. 从 Offline2.3.1.2 迁移

### 2.1 可直接复制的模块

| 模块 | 源文件 | 目标位置 | 说明 |
|---|---|---|---|
| Hook 系统 | `hooks.py` (2 KB) | `src/sdk/hooks.py` | 完全通用 |
| 日志系统 | `log.py` (3 KB) | `src/sdk/log.py` | 完全通用 |

**hooks.py 迁移**：

```python
# 源：Offline2.3.1.2/script/client/gui/mods/offhangar2/hooks.py
# 目标：src/sdk/hooks.py
# 修改：无（完全通用）
```

**log.py 迁移**：

```python
# 源：Offline2.3.1.2/script/client/gui/mods/offhangar2/log.py
# 目标：src/sdk/log.py
# 修改：修复 Decompyle++ artifact
```

### 2.2 需要适配的模块

| 模块 | 源文件 | 目标位置 | 适配内容 |
|---|---|---|---|
| 配置管理 | `config.py` (39 KB) | `src/sdk/config.py` | 移除单机特定配置，增加联机配置 |
| 装甲计算 | `armour.py` (23 KB) | `src/sdk/math/armour.py` | 移除 BigWorld 依赖 |
| 碰撞检测 | `tank_collision.py` (25 KB) | `src/sdk/math/collision.py` | 移除 BigWorld 依赖 |

**config.py 适配要点**：

```python
# 移除：
OFFLINE_URL = 'offline.local:20014'  # 单机假服务器
OFFLINE_NAME = 'OFFLINE (single player)'

# 增加：
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 28782
CLIENT_MODE = 'player'  # 'player' or 'worker'
ALLOW_MULTIPLE_CLIENTS = False
```

### 2.3 需要迁移到 sim-worker 的模块

| 模块 | 源文件 | 目标位置 | 迁移方式 |
|---|---|---|---|
| 驾驶模拟 | `drive.py` (206 KB) | `src/sim_worker/battle/movement.py` | 拆分 + 适配 |
| 射击机制 | `shooting.py` (179 KB) | `src/sim_worker/battle/shooting.py` | 拆分 + 适配 |
| 载具机制 | `mechanics.py` (243 KB) | `src/sim_worker/battle/mechanics.py` | 拆分 + 适配 |
| 炮塔控制 | `turret.py` (92 KB) | `src/sim_worker/battle/turret.py` | 拆分 + 适配 |
| 侦察系统 | `spotting.py` (53 KB) | `src/sim_worker/battle/spotting.py` | 拆分 + 适配 |
| Bot AI | `bots.py` (95 KB) | `src/sim_worker/ai/bot.py` | 拆分 + 适配 |
| 战斗生命周期 | `battle.py` (165 KB) | `src/sim_worker/battle/runtime.py` | 拆分 + 重写 |
| 生成逻辑 | `spawn.py` (76 KB) | `src/sim_worker/battle/spawn.py` | 拆分 + 适配 |
| 占领逻辑 | `capture.py` (15 KB) | `src/sim_worker/battle/capture.py` | 适配 |

**迁移原则**：

1. **移除 BigWorld 依赖**：sim-worker 不直接调用 BigWorld API
2. **移除客户端 UI**：sim-worker 不处理 UI
3. **保留核心逻辑**：物理、命中、伤害等核心算法保留
4. **适配数据格式**：从 BigWorld 实体改为协议消息格式

**drive.py 迁移示例**：

```python
# 源：Offline2.3.1.2/drive.py
# 问题：依赖 BigWorld.entity(), BigWorld.callback(), Math.Vector3
# 解决：
# 1. 将 BigWorld.entity() 改为内部实体管理器
# 2. 将 BigWorld.callback() 改为 tick 循环
# 3. 将 Math.Vector3 改为自定义 Vector3 或 numpy

# 目标：src/sim_worker/battle/movement.py
class MovementSystem:
    def __init__(self, entity_manager):
        self.entities = entity_manager
    
    def tick(self, dt):
        for vehicle in self.entities.vehicles:
            self._update_vehicle(vehicle, dt)
    
    def _update_vehicle(self, vehicle, dt):
        # 从 drive.py 迁移的物理逻辑
        # 移除 BigWorld 调用
        pass
```

### 2.4 需要保留在客户端的模块

| 模块 | 源文件 | 目标位置 | 说明 |
|---|---|---|---|
| 车库 UI | `hangar.py` (98 KB) | `src/client/ui/hangar.py` | 适配联机流程 |
| 战斗结果 | `results.py` (77 KB) | `src/client/ui/results.py` | 适配服务器结果 |
| 战斗通行证 | `battle_pass.py` (73 KB) | `src/client/ui/battle_pass.py` | 可选保留 |
| 模块/车组 | `modules_crew.py` (64 KB) | `src/client/ui/modules_crew.py` | 适配联机 |
| 开箱 | `lootboxes.py` (56 KB) | `src/client/ui/lootboxes.py` | 可选保留 |
| 招募 | `recruits.py` (46 KB) | `src/client/ui/recruits.py` | 可选保留 |
| 商店 | `store.py` (46 KB) | `src/client/ui/store.py` | 可选保留 |
| 炮塔渲染 | `turret.py` (92 KB) | `src/client/render/turret.py` | 只保留渲染部分 |

### 2.5 需要完全重写的模块

| 模块 | 源文件 | 重写原因 | 目标位置 |
|---|---|---|---|
| 假服务器 | `fake_server.py` (208 KB) | 单机命令处理 → 服务器权威 | `src/sim_worker/` |
| 假 Cell | `battle_server.py` (5 KB) | FakeCell → 真实网络连接 | `src/client/network/` |
| 离线登录 | `login.py` (19 KB) | 离线会话 → 联机会话 | `src/client/session.py` |
| 战斗会话 | `battle.py` (165 KB) | 单机战斗 → 联机战斗 | 拆分到 client/sim_worker |

## 3. 从参考项目迁移

### 3.1 可直接复用的模块

| 模块 | 源文件 | 目标位置 | 说明 |
|---|---|---|---|
| 协议语义 | `lan_client.py` 常量 | `src/protocol/constants.py` | 消息类型、能力协商 |
| 服务器骨架 | `lan_battle_server.py` | `src/sim_worker/server.py` | socketserver + tick |
| 快照同步 | `snapshot_sync.py` | `src/client/prediction/interpolation.py` | 纯数学插值 |
| 断线重连 | `lan_session.py` | `src/client/session.py` | 重连逻辑 |
| 窗口隐藏 | `instance_guard.py` | `src/multiclient/window_hider.py` | 窗口隐藏逻辑 |

### 3.2 需要适配的模块

| 模块 | 源文件 | 适配内容 |
|---|---|---|
| 协议客户端 | `lan_client.py` | 适配 2.3.1.2 数据格式 |
| 服务器逻辑 | `lan_battle_server.py` | 适配 2.3.1.2 战斗逻辑 |
| 等待房间 | `waiting_room_ui.py` | 适配 2.3.1.2 UI 系统 |
| 聊天 | `tactical_radio.py` | 适配 2.3.1.2 messenger API |

### 3.3 需要完全重写的模块

| 模块 | 源文件 | 重写原因 |
|---|---|---|
| 实例守卫 native | `offline_instance_guard_native.c` | 32-bit → 64-bit |
| Worker 启动器 | `offline_worker_starter.c` | 架构变化 |
| 兼容层 | `compat.py` | 2.3.1.2 API 变化 |
| 实体呈现 | `entities/*` | BigWorld ABI 变化 |
| UI hook | `lobby_ui.py`, `queue_*.py` | GUI 系统变化 |

## 4. 新建模块

### 4.1 协议层（`src/protocol/`）

**需要新建**：

| 文件 | 职责 |
|---|---|
| `messages.py` | 消息类型定义（dataclass） |
| `serializer.py` | JSON 序列化/反序列化 |
| `capabilities.py` | 能力协商逻辑 |
| `constants.py` | 协议常量 |

**参考**：`lan_client.py` 的消息定义和常量

### 4.2 SDK 扩展（`src/sdk/`）

**需要新建**：

| 文件 | 职责 |
|---|---|
| `math/vector.py` | 向量运算（替代 Math.Vector3） |
| `math/matrix.py` | 矩阵运算（替代 Math.Matrix） |
| `entity/base.py` | 实体基类 |
| `component/base.py` | 组件基类 |
| `event/bus.py` | 事件总线 |
| `interface/protocols.py` | 协议接口定义 |

### 4.3 客户端网络层（`src/client/network/`）

**需要新建**：

| 文件 | 职责 |
|---|---|
| `client.py` | TCP 客户端 |
| `connection.py` | 连接管理 |
| `reconnect.py` | 断线重连 |

**参考**：`lan_client.py` 的连接逻辑

### 4.4 客户端预测（`src/client/prediction/`）

**需要新建**：

| 文件 | 职责 |
|---|---|
| `local_player.py` | 本地玩家预测 |
| `interpolation.py` | 远程插值 |

**参考**：`snapshot_sync.py`

### 4.5 多实例 native（`src/multiclient/native/`）

**需要新建（x64 版本）**：

| 文件 | 职责 |
|---|---|
| `instance_guard.c` | x64 实例守卫 |
| `worker_starter.c` | x64 worker 启动器 |

**参考**：`offline_instance_guard_native.c`（需要重新逆向 2.3.1.2）

## 5. 迁移步骤

### 5.1 阶段 1：SDK 与协议

```bash
# 1. 创建 SDK 基础模块
src/sdk/hooks.py          # 从 Offline2.3.1.2 复制
src/sdk/log.py            # 从 Offline2.3.1.2 复制
src/sdk/config.py         # 从 Offline2.3.1.2 适配
src/sdk/math/vector.py    # 新建
src/sdk/math/matrix.py    # 新建

# 2. 创建协议层
src/protocol/messages.py      # 新建
src/protocol/serializer.py    # 新建
src/protocol/constants.py     # 新建
src/protocol/capabilities.py  # 新建

# 3. 测试
tests/unit/test_protocol.py
tests/unit/test_serializer.py
```

### 5.2 阶段 2：服务器骨架

```bash
# 1. 创建服务器基础
src/sim_worker/main.py         # 新建
src/sim_worker/server.py       # 从参考项目适配
src/sim_worker/tick.py         # 新建

# 2. 创建房间管理
src/sim_worker/room/room.py    # 从参考项目适配
src/sim_worker/room/lobby.py   # 新建

# 3. 测试
tests/integration/test_server.py
```

### 5.3 阶段 3：战斗逻辑迁移

```bash
# 1. 从 Offline2.3.1.2 迁移战斗逻辑
src/sim_worker/battle/movement.py   # 从 drive.py 迁移
src/sim_worker/battle/shooting.py   # 从 shooting.py 迁移
src/sim_worker/battle/mechanics.py  # 从 mechanics.py 迁移
src/sim_worker/battle/turret.py     # 从 turret.py 迁移
src/sim_worker/battle/spotting.py   # 从 spotting.py 迁移
src/sim_worker/battle/damage.py     # 从 shooting.py 迁移

# 2. 迁移 Bot AI
src/sim_worker/ai/bot.py           # 从 bots.py 迁移
src/sim_worker/ai/planner.py       # 从 bot_routes.py 迁移

# 3. 测试
tests/unit/test_movement.py
tests/unit/test_shooting.py
tests/integration/test_battle.py
```

### 5.4 阶段 4：客户端网络与预测

```bash
# 1. 创建客户端网络层
src/client/network/client.py       # 从参考项目适配
src/client/network/connection.py   # 新建
src/client/network/reconnect.py    # 新建

# 2. 创建预测层
src/client/prediction/local_player.py    # 新建
src/client/prediction/interpolation.py   # 从参考项目适配

# 3. 测试
tests/unit/test_prediction.py
tests/integration/test_client.py
```

### 5.5 阶段 5：客户端 UI/Hook

```bash
# 1. 创建客户端入口
src/client/mod_entry.py            # 新建
src/client/bootstrap.py            # 从参考项目适配
src/client/session.py              # 从 Offline2.3.1.2 适配

# 2. 迁移 UI
src/client/ui/hangar.py            # 从 Offline2.3.1.2 适配
src/client/ui/waiting_room.py      # 从参考项目适配
src/client/ui/battle.py            # 从 Offline2.3.1.2 适配

# 3. 迁移 Hook
src/client/hooks/avatar.py         # 新建
src/client/hooks/vehicle.py        # 新建
src/client/hooks/account.py        # 新建

# 4. 测试
tests/integration/test_ui.py
```

### 5.6 阶段 6：多实例

```bash
# 1. 逆向 2.3.1.2 WGC 结构
tools/reverse_engineering/pe_analyzer.py
tools/reverse_engineering/mutex_finder.py

# 2. 编写 x64 native
src/multiclient/native/instance_guard.c
src/multiclient/native/worker_starter.c

# 3. 编译
src/multiclient/native/build.ps1

# 4. 测试
tests/unit/test_instance_guard.py
```

### 5.7 阶段 7：启动器与部署

```bash
# 1. 创建启动器
src/launcher/main.py
src/launcher/args.py
src/launcher/deploy.py
src/launcher/process.py

# 2. 创建部署脚本
src/deploy/build.py
src/deploy/install.py
src/deploy/templates/config.json

# 3. 测试
tests/integration/test_launcher.py
```

## 6. 依赖库选型

### 6.1 客户端（Python 2.7）

| 库 | 版本 | 许可证 | 用途 | Windows |
|---|---|---|---|---|
| `socket` | 标准库 | PSF | 网络 | ✓ |
| `json` | 标准库 | PSF | 序列化 | ✓ |
| `threading` | 标准库 | PSF | 多线程 | ✓ |
| `ctypes` | 标准库 | PSF | Windows API | ✓ |
| `logging` | 标准库 | PSF | 日志 | ✓ |
| `math` | 标准库 | PSF | 数学 | ✓ |

**注意**：客户端必须使用 Python 2.7，只能用标准库。

### 6.2 服务器（Python 3）

| 库 | 版本 | 许可证 | 用途 | Windows |
|---|---|---|---|---|
| `asyncio` | 3.4+ | PSF | 异步 IO | ✓ |
| `socketserver` | 标准库 | PSF | TCP 服务器 | ✓ |
| `json` | 标准库 | PSF | 序列化 | ✓ |
| `dataclasses` | 3.7+ | PSF | 数据类 | ✓ |
| `typing` | 3.5+ | PSF | 类型注解 | ✓ |
| `logging` | 标准库 | PSF | 日志 | ✓ |
| `numpy` | 1.20+ | BSD | 数学（可选） | ✓ |
| `pytest` | 7.0+ | MIT | 测试 | ✓ |
| `psutil` | 5.9+ | BSD | 进程管理 | ✓ |

### 6.3 启动器（Python 3）

| 库 | 版本 | 许可证 | 用途 | Windows |
|---|---|---|---|---|
| `argparse` | 标准库 | PSF | 参数解析 | ✓ |
| `subprocess` | 标准库 | PSF | 进程管理 | ✓ |
| `pathlib` | 3.4+ | PSF | 路径处理 | ✓ |
| `shutil` | 标准库 | PSF | 文件操作 | ✓ |
| `psutil` | 5.9+ | BSD | 进程管理 | ✓ |

### 6.4 Native C

| 库 | 版本 | 许可证 | 用途 | Windows |
|---|---|---|---|---|
| Windows SDK | — | — | Win32 API | ✓ |
| MinGW-w64 | — | — | 编译器 | ✓ |

## 7. 测试计划

### 7.1 单元测试

| 测试文件 | 测试内容 |
|---|---|
| `test_protocol.py` | 协议消息定义 |
| `test_serializer.py` | JSON 序列化/反序列化 |
| `test_vector.py` | 向量运算 |
| `test_movement.py` | 移动逻辑 |
| `test_shooting.py` | 射击逻辑 |
| `test_prediction.py` | 预测逻辑 |
| `test_instance_guard.py` | 实例守卫 |

### 7.2 集成测试

| 测试文件 | 测试内容 |
|---|---|
| `test_server.py` | 服务器启动、tick 循环 |
| `test_client.py` | 客户端连接、消息收发 |
| `test_battle.py` | 完整战斗流程 |
| `test_reconnect.py` | 断线重连 |
| `test_launcher.py` | 启动器部署 |

### 7.3 端到端测试

| 测试文件 | 测试内容 |
|---|---|
| `test_multiplayer.py` | 多客户端联机 |
| `test_authority.py` | 权威状态一致性 |
| `test_performance.py` | 性能指标 |

## 8. 风险与缓解

| 风险 | 等级 | 缓解措施 |
|---|---|---|
| x64 native 重写 | **高** | 专门的逆向任务，逐步验证 |
| BigWorld API 变化 | **中** | 从 Offline2.3.1.2 提取 API 用法 |
| 机制系统复杂度 | **中** | 分模块迁移，逐步验证 |
| Python 2.7 限制 | **低** | 客户端只用标准库 |
| 性能问题 | **中** | 性能测试，优化关键路径 |

## 9. 时间估计

| 阶段 | 工作量 | 依赖 |
|---|---|---|
| 阶段 1：SDK 与协议 | 2-3 天 | 无 |
| 阶段 2：服务器骨架 | 2-3 天 | 阶段 1 |
| 阶段 3：战斗逻辑迁移 | 5-7 天 | 阶段 2 |
| 阶段 4：客户端网络与预测 | 3-4 天 | 阶段 1 |
| 阶段 5：客户端 UI/Hook | 5-7 天 | 阶段 4 |
| 阶段 6：多实例 | 3-5 天 | 逆向分析 |
| 阶段 7：启动器与部署 | 2-3 天 | 阶段 2-5 |
| **总计** | **22-32 天** | — |

**注意**：多实例逆向分析可能需要更长时间，取决于 2.3.1.2 的 WGC 结构复杂度。
