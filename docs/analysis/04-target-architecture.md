# 04 - 目标架构设计

> 设计时间：2026-09-12
> 目标：将 Offline2.3.1.2 改造为服务器权威的联机架构

## 1. 架构总览

### 1.1 设计原则

1. **服务器权威**：sim-worker 决定所有游戏状态（移动、炮塔、开火、命中、伤害、死亡）
2. **薄客户端**：客户端只负责输入、渲染、UI、预测
3. **单人也联机**：即使只有一个人，也必须连接本地 sim-worker
4. **不保留单机模式**：不提供离线单机路径
5. **断线重连**：支持网络断开后重新连接
6. **模块化**：代码按职责分离，避免大文件

### 1.2 运行时架构

```
┌─────────────────────────────────────────────────────────────┐
│                   可见玩家客户端 (thin)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │    输入      │  │    渲染      │  │     UI      │         │
│  └──────┬──────┘  └──────▲──────┘  └──────▲──────┘         │
│         │                │                │                  │
│  ┌──────▼──────────────────────────────────────────────┐    │
│  │              客户端预测 + 插值                        │    │
│  │  本地物理跑自己的坦克                                  │    │
│  │  远程车辆用确认样本插值                                │    │
│  └──────┬──────────────────────────▲───────────────────┘    │
│         │                          │                        │
└─────────┼──────────────────────────┼────────────────────────┘
          │ TCP JSON lines           │ TCP JSON lines
          ▼                          │
┌─────────────────────────────────────────────────────────────┐
│                   LAN 服务器 (Python 3)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  房间管理    │  │  消息中继    │  │  状态快照    │         │
│  └──────┬──────┘  └──────▲──────┘  └──────▲──────┘         │
│         │                │                │                  │
│  ┌──────▼──────────────────────────────────────────────┐    │
│  │              30 Hz 世界 tick                         │    │
│  │              15 Hz 快照广播                          │    │
│  └──────┬──────────────────────────▲───────────────────┘    │
│         │                          │                        │
└─────────┼──────────────────────────┼────────────────────────┘
          │ TCP JSON lines           │ TCP JSON lines
          ▼                          │
┌─────────────────────────────────────────────────────────────┐
│              隐藏仿真 Worker (权威)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Bot AI    │  │   弹道计算   │  │   碰撞检测   │         │
│  └──────┬──────┘  └──────▲──────┘  └──────▲──────┘         │
│         │                │                │                  │
│  ┌──────▼──────────────────────────────────────────────┐    │
│  │              完整游戏客户端进程                       │    │
│  │              native 战斗空间                          │    │
│  │              地形/模型/命中检测                        │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  隐藏窗口（私有 desktop）                                     │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 数据流

```
玩家输入 → 客户端 → 服务器 → Worker（权威计算）→ 服务器 → 所有客户端
         send_input        process_input      bot_state
                                                projectile_*
                                                snapshot
```

## 2. 目录结构

```
D:\Projects\vvg-offline-battles\
├── AGENTS.md                           # Agent 入口文件
├── .gitignore
├── pyproject.toml                      # 项目配置
├── README.md
│
├── docs/
│   ├── analysis/                       # 第一阶段分析文档
│   │   ├── 01-offline2312-project-scan.md
│   │   ├── 02-reference-wot-offline-battles-scan.md
│   │   ├── 03-version-diff-0.9.22-vs-2.3.1.2.md
│   │   ├── 04-target-architecture.md
│   │   ├── 05-migration-and-sdk-plan.md
│   │   ├── 06-task-breakdown.md
│   │   └── 07-risks-and-open-questions.md
│   ├── agent/                          # Agent 交接文档
│   │   ├── PROGRESS.md
│   │   ├── HANDOFF.md
│   │   ├── DECISIONS.md
│   │   └── OPEN_QUESTIONS.md
│   └── design/                         # 详细设计文档
│       ├── protocol.md
│       ├── sim-worker.md
│       ├── client.md
│       └── multiclient.md
│
├── src/
│   ├── sdk/                            # 可复用 SDK
│   │   ├── __init__.py
│   │   ├── hooks.py                    # Hook 系统（从 Offline2.3.1.2 抽取）
│   │   ├── log.py                      # 日志系统
│   │   ├── config.py                   # 配置管理
│   │   ├── math/                       # 数学库
│   │   │   ├── __init__.py
│   │   │   ├── vector.py
│   │   │   └── matrix.py
│   │   ├── entity/                     # 实体系统
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   └── vehicle.py
│   │   ├── component/                  # 组件系统
│   │   │   ├── __init__.py
│   │   │   └── base.py
│   │   ├── event/                      # 事件系统
│   │   │   ├── __init__.py
│   │   │   └── bus.py
│   │   └── interface/                  # 接口定义
│   │       ├── __init__.py
│   │       └── protocols.py
│   │
│   ├── protocol/                       # 协议定义
│   │   ├── __init__.py
│   │   ├── messages.py                 # 消息类型定义
│   │   ├── serializer.py               # 序列化/反序列化
│   │   ├── capabilities.py             # 能力协商
│   │   └── constants.py                # 协议常量
│   │
│   ├── sim_worker/                     # 权威服务器
│   │   ├── __init__.py
│   │   ├── main.py                     # 入口
│   │   ├── server.py                   # TCP 服务器
│   │   ├── tick.py                     # 世界 tick 循环
│   │   ├── room/                       # 房间管理
│   │   │   ├── __init__.py
│   │   │   ├── room.py
│   │   │   ├── lobby.py
│   │   │   └── matchmaking.py
│   │   ├── battle/                     # 战斗逻辑
│   │   │   ├── __init__.py
│   │   │   ├── runtime.py
│   │   │   ├── movement.py
│   │   │   ├── turret.py
│   │   │   ├── shooting.py
│   │   │   ├── damage.py
│   │   │   ├── spotting.py
│   │   │   └── capture.py
│   │   ├── ai/                         # Bot AI
│   │   │   ├── __init__.py
│   │   │   ├── bot.py
│   │   │   ├── planner.py
│   │   │   └── navigation.py
│   │   ├── physics/                    # 物理计算
│   │   │   ├── __init__.py
│   │   │   ├── vehicle.py
│   │   │   ├── projectile.py
│   │   │   └── collision.py
│   │   └── state/                      # 状态管理
│   │       ├── __init__.py
│   │       ├── snapshot.py
│   │       └── authority.py
│   │
│   ├── client/                         # 薄客户端补丁
│   │   ├── __init__.py
│   │   ├── mod_entry.py                # BigWorld mod 入口
│   │   ├── bootstrap.py                # 初始化
│   │   ├── session.py                  # 会话管理
│   │   ├── network/                    # 网络层
│   │   │   ├── __init__.py
│   │   │   ├── client.py               # TCP 客户端
│   │   │   └── connection.py           # 连接管理
│   │   ├── prediction/                 # 客户端预测
│   │   │   ├── __init__.py
│   │   │   ├── local_player.py
│   │   │   └── interpolation.py
│   │   ├── render/                     # 渲染呈现
│   │   │   ├── __init__.py
│   │   │   ├── entities.py
│   │   │   └── projectiles.py
│   │   ├── ui/                         # UI 补丁
│   │   │   ├── __init__.py
│   │   │   ├── hangar.py
│   │   │   ├── battle.py
│   │   │   └── waiting_room.py
│   │   └── hooks/                      # BigWorld hook
│   │       ├── __init__.py
│   │       ├── avatar.py
│   │       ├── vehicle.py
│   │       └── account.py
│   │
│   ├── multiclient/                    # 多实例限制解除
│   │   ├── __init__.py
│   │   ├── instance_guard.py           # 实例守卫 Python 接口
│   │   ├── native/                     # Native C 源码
│   │   │   ├── instance_guard.c        # x64 版本
│   │   │   └── worker_starter.c        # worker 启动器
│   │   └── window_hider.py             # 窗口隐藏
│   │
│   ├── launcher/                       # 命令行启动器
│   │   ├── __init__.py
│   │   ├── main.py                     # 入口
│   │   ├── args.py                     # 参数解析
│   │   ├── deploy.py                   # 部署逻辑
│   │   └── process.py                  # 进程管理
│   │
│   └── deploy/                         # 部署脚本
│       ├── __init__.py
│       ├── build.py                    # 构建脚本
│       ├── install.py                  # 安装脚本
│       └── templates/                  # 模板文件
│           ├── config.json
│           └── server_endpoint.json
│
├── tests/                              # 测试
│   ├── __init__.py
│   ├── unit/                           # 单元测试
│   │   ├── __init__.py
│   │   ├── test_protocol.py
│   │   ├── test_serializer.py
│   │   ├── test_snapshot.py
│   │   └── test_math.py
│   ├── integration/                    # 集成测试
│   │   ├── __init__.py
│   │   ├── test_server.py
│   │   ├── test_client.py
│   │   └── test_battle.py
│   └── fixtures/                       # 测试数据
│       ├── __init__.py
│       └── sample_messages.py
│
├── tools/                              # 辅助工具
│   ├── bake_navigation.py              # 导航图烘焙
│   ├── bake_foliage.py                 # 植被烘焙
│   ├── extract_api.py                  # API 提取
│   └── reverse_engineering/            # 逆向工具
│       ├── pe_analyzer.py
│       └── mutex_finder.py
│
└── vendor/                             # 第三方依赖
    └── README.md
```

## 3. 模块详细设计

### 3.1 SDK (`src/sdk/`)

**职责**：提供可复用的基础组件，与游戏版本无关。

**核心模块**：

| 模块 | 职责 | 来源 |
|---|---|---|
| `hooks.py` | 方法替换装饰器 | 从 Offline2.3.1.2 抽取 |
| `log.py` | 日志系统 | 从 Offline2.3.1.2 抽取 |
| `config.py` | 配置管理 | 从 Offline2.3.1.2 抽取（适配） |
| `math/` | 向量/矩阵数学 | 新建（或用 numpy） |
| `entity/` | 实体基类 | 新建 |
| `component/` | 组件基类 | 新建 |
| `event/` | 事件总线 | 新建 |
| `interface/` | 协议接口定义 | 新建 |

### 3.2 协议 (`src/protocol/`)

**职责**：定义客户端-服务器-Worker 之间的消息协议。

**设计**：参考 0.9.22 的 JSON lines 协议，适配 2.3.1.2 的数据格式。

**核心消息类型**：

```python
# 客户端 → 服务器
HELLO = "hello"                    # 首帧，携带 capabilities
INPUT = "input"                    # 玩家输入帧
FIRE_INTENT = "fire_intent"        # 开火意图
LEAVE_BATTLE = "leave_battle"      # 离开战斗
PING = "ping"                      # 心跳

# 服务器 → 客户端
WELCOME = "welcome"                # 欢迎响应
SNAPSHOT = "snapshot"              # 状态快照（15 Hz）
BOT_MANIFEST = "bot_manifest"      # Bot 名册
BOT_STATE = "bot_state"            # Bot 状态
PROJECTILE_LAUNCH = "projectile_launch"  # 弹道发射
PROJECTILE_HIT = "projectile_hit"  # 弹道命中
DESTRUCTIBLE = "destructible"      # 可破坏物状态
RULES_STATE = "rules_state"        # 规则状态
BATTLE_RESULT = "battle_result"    # 战斗结果

# Worker → 服务器
BOT_AUTHORITY_STATE = "bot_authority_state"  # 权威 Bot 状态
BOT_OBSERVATION = "bot_observation"          # Bot 观测
```

**序列化**：JSON（UTF-8，换行分隔）

**能力协商**：

```python
CAPABILITIES = {
    "protocol_version": 1,
    "client_build": "vvg-2.3.1.2",
    "features": [
        "projectile_ledger_v1",
        "spotting_v1",
        "destructible_v1",
        "reconnect_v1",
    ],
}
```

### 3.3 sim-worker (`src/sim_worker/`)

**职责**：权威服务器，运行完整游戏逻辑。

**核心组件**：

| 组件 | 职责 | 参考 |
|---|---|---|
| `server.py` | TCP 服务器 | `lan_battle_server.py` |
| `tick.py` | 30 Hz 世界 tick | `lan_battle_server.py` |
| `room/` | 房间管理 | `lan_battle_server.py` |
| `battle/runtime.py` | 战斗运行时 | `battle_runtime.py` + Offline2.3.1.2 |
| `battle/movement.py` | 移动权威 | Offline2.3.1.2 `drive.py` |
| `battle/turret.py` | 炮塔权威 | Offline2.3.1.2 `turret.py` |
| `battle/shooting.py` | 开火权威 | Offline2.3.1.2 `shooting.py` |
| `battle/damage.py` | 伤害权威 | Offline2.3.1.2 `shooting.py` |
| `battle/spotting.py` | 侦察权威 | Offline2.3.1.2 `spotting.py` |
| `ai/` | Bot AI | Offline2.3.1.2 `bots.py` + 参考项目 |
| `physics/` | 物理计算 | Offline2.3.1.2 `drive.py` + `shooting.py` |
| `state/snapshot.py` | 状态快照 | 参考项目 `snapshot_sync.py` |

**运行方式**：
- Python 3 独立进程
- 不依赖游戏客户端
- 可选：嵌入 native 战斗空间（用于地形/模型/命中检测）

### 3.4 薄客户端 (`src/client/`)

**职责**：输入、渲染、UI、预测。

**核心组件**：

| 组件 | 职责 | 参考 |
|---|---|---|
| `mod_entry.py` | BigWorld mod 入口 | `mod_offline_lan_0922.py` |
| `bootstrap.py` | 初始化 | `bootstrap.py` |
| `session.py` | 会话管理 | `lan_session.py` |
| `network/client.py` | TCP 客户端 | `lan_client.py` |
| `prediction/local_player.py` | 本地玩家预测 | `snapshot_sync.py` |
| `prediction/interpolation.py` | 远程插值 | `snapshot_sync.py` |
| `render/entities.py` | 实体呈现 | 参考项目 `entities/` |
| `ui/` | UI 补丁 | Offline2.3.1.2 `hangar.py` + 参考项目 |
| `hooks/` | BigWorld hook | Offline2.3.1.2 `hooks.py` + 参考项目 |

**部署方式**：
- 编译为 `.pyc`
- 放置到 `res_mods/2.3.1.2/scripts/client/gui/mods/`
- 或打包为 `.wotmod` 放置到 `mods/2.3.1.2/`

### 3.5 多实例 (`src/multiclient/`)

**职责**：解除游戏单实例限制。

**核心组件**：

| 组件 | 职责 | 参考 |
|---|---|---|
| `instance_guard.py` | Python 接口 | `instance_guard.py` |
| `native/instance_guard.c` | x64 native 实现 | **必须重写** |
| `native/worker_starter.c` | worker 启动器 | `worker_starter.c`（适配 x64） |
| `window_hider.py` | 窗口隐藏 | 参考项目 |

**环境变量**：

```bash
VVG_ALLOW_MULTIPLE_CLIENTS=1      # 启用多实例
VVG_CLIENT_MODE=player|worker      # 客户端模式
VVG_SERVER_HOST=127.0.0.1          # 服务器地址
VVG_SERVER_PORT=28782              # 服务器端口
```

### 3.6 启动器 (`src/launcher/`)

**职责**：命令行启动器。

**功能**：

```bash
# 部署 mod 到游戏
vvg-launcher deploy --game-root "D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2"

# 启动 sim-worker
vvg-launcher start-worker

# 启动客户端（player 模式）
vvg-launcher start-player

# 启动客户端（worker 模式）
vvg-launcher start-worker-client

# 启动完整游戏（服务器 + worker + player）
vvg-launcher start-game
```

### 3.7 部署 (`src/deploy/`)

**职责**：构建和部署脚本。

**功能**：
- 编译 `.py` → `.pyc`
- 打包 `.wotmod`
- 安装到游戏目录
- 配置文件管理

## 4. 关键设计决策

### 4.1 协议设计

**决策**：使用 JSON lines over TCP

**理由**：
- 参考项目已验证可行
- 可读性好，调试方便
- Python 标准库支持
- 性能足够（LAN 环境）

**备选**：MessagePack（更高效，但可读性差）

### 4.2 服务器语言

**决策**：Python 3

**理由**：
- 参考项目使用 Python 3
- asyncio 支持好
- 不受客户端 Python 2.7 限制
- 可用现代 Python 特性

### 4.3 客户端语言

**决策**：Python 2.7（必须）

**理由**：
- 游戏内嵌 Python 2.7
- 无法升级

### 4.4 多实例方案

**决策**：native C x64 + 引擎 WGC cleanup thunk

**理由**：
- 参考项目已验证类似方案
- 0.9.22 的 32-bit 方案无法直接使用
- 需要为 2.3.1.2 重新逆向

**风险**：需要逆向 2.3.1.2 的 WGC 结构

### 4.5 预测模型

**决策**：本地玩家本地物理，远程确认样本插值

**理由**：
- 参考项目已验证
- 本地玩家体验好
- 远程车辆平滑

## 5. 接口定义

### 5.1 客户端 → 服务器

```python
# hello 消息
{
    "type": "hello",
    "protocol_version": 1,
    "client_build": "vvg-2.3.1.2",
    "capabilities": ["projectile_ledger_v1", ...],
    "player_name": "Player1",
}

# input 消句
{
    "type": "input",
    "seq": 12345,
    "time": 123456.789,
    "movement": {
        "forward": 0.5,
        "right": 0.0,
        "brake": 0.0,
    },
    "turret": {
        "yaw": 1.57,
        "pitch": 0.1,
    },
    "fire": False,
    "siege": False,
}

# fire_intent 消息
{
    "type": "fire_intent",
    "seq": 12346,
    "time": 123456.800,
    "shell_index": 0,
    "target_point": [x, y, z],  # 可选
}
```

### 5.2 服务器 → 客户端

```python
# welcome 消息
{
    "type": "welcome",
    "protocol_version": 1,
    "role": "player",
    "server_build": "vvg-0.1.0",
    "capabilities": [...],
    "room_id": "room-123",
    "player_id": 1,
    "team": 1,
}

# snapshot 消息（15 Hz）
{
    "type": "snapshot",
    "tick": 12345,
    "time": 123456.789,
    "phase": "battle",
    "vehicles": [
        {
            "id": 1,
            "team": 1,
            "alive": True,
            "health": 1000,
            "max_health": 1000,
            "position": [x, y, z],
            "rotation": [yaw, pitch, roll],
            "turret_yaw": 1.57,
            "gun_pitch": 0.1,
            "velocity": [vx, vy, vz],
        },
        ...
    ],
    "projectiles": [
        {
            "id": 1001,
            "owner_id": 1,
            "origin": [x, y, z],
            "velocity": [vx, vy, vz],
            "gravity": 9.81,
            "shell_type": "AP",
        },
        ...
    ],
}
```

### 5.3 Worker → 服务器

```python
# bot_authority_state 消息
{
    "type": "bot_authority_state",
    "worker_id": "worker-1",
    "authority_epoch": 1,
    "tick": 12345,
    "bots": [
        {
            "id": 2,
            "team": 2,
            "alive": True,
            "health": 800,
            "position": [x, y, z],
            "rotation": [yaw, pitch, roll],
            "turret_yaw": 1.2,
            "gun_pitch": 0.05,
            "target_id": 1,
            "state": "attacking",
        },
        ...
    ],
}
```

## 6. 部署架构

### 6.1 开发环境

```
D:\Projects\vvg-offline-battles\
├── src/           # 源码
├── tests/         # 测试
└── tools/         # 工具

D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\
├── res_mods\2.3.1.2\scripts\client\gui\mods\  # 部署的客户端 mod
├── mods\2.3.1.2\                               # wotmod（可选）
└── mods\configs\vvg_offline\                   # 配置文件
```

### 6.2 生产环境

```
游戏根目录\
├── WorldOfTanks.exe
├── win64\
│   └── python27.dll
├── res_mods\2.3.1.2\scripts\client\gui\mods\
│   ├── mod_vvg_offline.py                     # 入口
│   └── vvg_offline\                           # 主包
│       ├── __init__.py
│       ├── bootstrap.py
│       ├── network\
│       ├── prediction\
│       ├── render\
│       ├── ui\
│       └── hooks\
├── mods\2.3.1.2\
│   └── org.vvg.offline_battles_0.1.0.wotmod  # 可选
└── mods\configs\vvg_offline\
    ├── config.json
    └── server_endpoint.json
```

## 7. 测试策略

### 7.1 单元测试

- 协议序列化/反序列化
- 数学库
- 状态快照
- 房间管理逻辑

### 7.2 集成测试

- 服务器 tick 循环
- 客户端连接
- 战斗流程
- 断线重连

### 7.3 端到端测试

- 多客户端联机
- 权威状态一致性
- 性能指标

## 8. 性能目标

| 指标 | 目标 | 说明 |
|---|---|---|
| 服务器 tick | 30 Hz | 世界更新频率 |
| 快照频率 | 15 Hz | 状态广播频率 |
| 网络延迟 | < 50 ms | LAN 环境 |
| 客户端帧率 | 60 FPS | 渲染帧率 |
| 最大玩家 | 30 | 房间容量 |
| 最大 Bot | 30 | 每房间 |

## 9. 安全考虑

- **不做反作弊**：用户明确要求
- **服务器权威**：仍然保持服务器权威，防止客户端篡改
- **输入验证**：服务器验证客户端输入的合法性
- **资源限制**：限制消息大小、频率

## 10. 扩展性

### 10.1 模式扩展

- 标准战斗（15v15）
- 车库战（任意车辆）
- 自定义房间

### 10.2 地图扩展

- 从 Offline2.3.1.2 提取地图数据
- 烘焙导航图
- 烘焙植被数据

### 10.3 Bot 扩展

- 从 Offline2.3.1.2 提取 Bot AI
- 从参考项目提取导航
- 自定义 Bot 阵容
