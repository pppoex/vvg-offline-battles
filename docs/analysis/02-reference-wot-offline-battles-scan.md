# 02 - wot-offline-battles 参考项目扫描报告

> 扫描时间：2026-09-12
> 扫描范围：`D:\Projects\wot-offline-battles`（只读参考）
> 目标客户端：坦克世界 0.9.22.0.1 #1513（中国区 HD，32-bit x86）

## 1. 项目概览

| 属性 | 值 | 证据 |
|---|---|---|
| 项目版本 | 0.7.7 | `launcher/wot_launcher.py:46`: `LAUNCHER_VERSION = "0.7.7"` |
| 目标客户端 | 0.9.22.0.1 #1513 | `README.md:3-4` |
| 客户端架构 | 32-bit x86 | `COMPATIBILITY_REVIEW.md`: "The executable is 32-bit x86" |
| Python 版本 | 客户端 Py2.7.7 / 服务器 Py3 | bytecode magic `03 f3 0d 0a`；server 用 `from __future__ import annotations` |
| 协议版本 | 5 | `lan_client.py:31`: `PROTOCOL_VERSION = 5` |
| 服务器端口 | 28782 | `windows_server.py:17`: `SERVER_PORT = 28782` |
| 服务器 Tick | 30 Hz | `lan_battle_server.py:75`: `TICK_HZ = 30.0` |
| 快照频率 | 15 Hz | `lan_battle_server.py:79`: `REPLICA_SNAPSHOT_HZ = 15.0` |
| 文件总数 | ~604 个 | `Get-ChildItem -Recurse -File` |

## 2. 整体架构

### 2.1 核心设计

```
┌─────────────────────────────────────────────────────────────┐
│                     可见玩家客户端 (thin)                     │
│  输入 → 发送 input/fire_intent                              │
│  渲染 ← 接收 replica snapshots                              │
│  预测：本地物理跑自己的坦克                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ TCP JSON lines
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   LAN 服务器 (Python 3)                      │
│  socketserver TCP + JSON lines                              │
│  30 Hz 世界 tick                                            │
│  15 Hz 副本快照广播                                          │
│  房间管理、队伍分配、消息中继                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │ TCP JSON lines
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              隐藏仿真 Worker (权威)                           │
│  完整游戏客户端进程（headless）                               │
│  Bot AI、弹道、碰撞、伤害、侦察 全部权威                       │
│  使用 native 战斗空间做地形/模型/命中检测                      │
│  隐藏窗口（私有 desktop）                                     │
└─────────────────────────────────────────────────────────────┘
```

**关键原则**（`CLAUDE.md:182-191`）：

> Every room has one mandatory hidden native worker. The only simulation path is `visible client -> LAN server -> hidden worker -> LAN server -> replicas`. Visible clients submit player input and fire intent; they never become Bot or projectile authority.

### 2.2 目录结构

```
wot-offline-battles/
├── src/res/scripts/client/gui/mods/
│   ├── mod_offline_lan_0922.py          # wotmod 入口（9 行）
│   └── offline_lan_0922/                # 主包（~100 个模块）
│       ├── bootstrap.py                 # 初始化
│       ├── lan_client.py                # 协议客户端
│       ├── lan_session.py               # 会话协调
│       ├── battle_runtime.py            # 战斗运行时
│       ├── snapshot_sync.py             # 快照→实体
│       ├── authority_worker.py          # worker 生命周期
│       ├── instance_guard.py            # 多实例守卫
│       ├── compat.py                    # 0.9.22 兼容层
│       ├── entities/                    # 实体呈现
│       ├── ai/                          # Bot AI
│       ├── account_rpc/                 # 账户 RPC
│       └── ...（约 80 个模块）
├── server/
│   ├── lan_battle_server.py             # 主服务器（~15000 行）
│   ├── windows_server.py                # Windows 入口
│   ├── server_bot_ai.py                 # 服务器端 Bot
│   └── offline_rewards.py               # 离线奖励
├── launcher/
│   ├── wot_launcher.py                  # 桌面启动器（~3500 行）
│   ├── core.py                          # 核心逻辑
│   └── ...（UI/配置模块）
├── native/
│   ├── offline_instance_guard_native.c  # 实例守卫 C 源码
│   ├── offline_instance_guard_native.pyd # 编译产物
│   ├── offline_worker_starter.c         # worker 启动器 C 源码
│   └── offline_worker_starter.exe       # 编译产物
├── tests/                               # ~130 个测试文件
├── tools/                               # 烘焙/审计工具
├── navgraphs/ foliage/ destructibles/   # 41 张地图数据
├── client_overlay/                      # preferences XML
└── build_wotmod.py                      # 打包脚本
```

## 3. 网络层与协议

### 3.1 传输层

| 项 | 值 | 证据 |
|---|---|---|
| 协议 | TCP | `lan_client.py:3419`: `socket.socket(socket.AF_INET, socket.SOCK_STREAM)` |
| 序列化 | JSON lines | `json.dumps(...) + '\n'` |
| 编码 | UTF-8 | `.encode('utf-8')` |
| TCP_NODELAY | 启用 | `sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)` |
| 单行上限 | 256 KB | `MAX_LINE_BYTES = 256 * 1024` |
| 轮询间隔 | 1/60 秒 | `POLL_INTERVAL = 1.0 / 60.0` |
| PING 间隔 | 1 秒 | `PING_INTERVAL = 1.0` |

### 3.2 协议消息类型

**客户端 → 服务器**：
- `hello` — 首帧，携带 capabilities
- `input` — 玩家输入帧
- `fire_intent` — 开火意图
- `leave_battle` — 离开战斗
- `ping` — 心跳

**服务器 → 客户端**：
- `welcome` — 欢迎响应（协议、role、round_id 等）
- `snapshot` — 15 Hz 状态快照
- `bot_manifest` — Bot 名册（每 5 秒刷新）
- `bot_state` — Bot 状态行
- `projectile_*` — 弹道事件
- `destructible` — 可破坏物状态
- `rules_state` — 规则状态
- `battle_result` — 战斗结果

**Worker → 服务器**：
- `bot_state` — 权威 Bot 状态
- `bot_observation` — Bot 观测
- `bot_ram_report` — 撞击报告
- `projectile_ledger` — 弹道账本

### 3.3 能力协商

```
lan_client.py:31-56
PROJECTILE_LEDGER_CAPABILITY = 'projectile_ledger_v2'
RICOCHET_CONTINUATION_CAPABILITY = 'ricochet_continuation_v1'
DESTRUCTIBLE_CATALOG_V5_CAPABILITY = 'destructible_catalog_v5'
LEAN_SNAPSHOT_MANIFEST_CAPABILITY = 'lean_snapshot_manifest_v1'
RAM_CONTACT_LEDGER_CAPABILITY = 'ram_contact_ledger_v2'
HUMAN_RAM_TIMELINE_CAPABILITY = 'human_ram_timeline_v1'
PLAYER_FIRE_INTENT_CAPABILITY = 'player_fire_intent_v6'
PLAYER_ENVIRONMENT_CAPABILITY = 'player_environment_v2'
EFFECTIVE_PARAMS_CAPABILITY = ...
SIMULATION_WORKER_CAPABILITY = 'simulation_worker_v1'
```

第一帧必须是 `hello`；协商失败在入战前拒绝。

### 3.4 服务器架构

```python
# lan_battle_server.py:13971
class ClientHandler(socketserver.BaseRequestHandler):
    # 处理单个客户端连接

# lan_battle_server.py:14790
class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
```

**Worker 专用 welcome**（line 13973-13996）：

```python
_worker_welcome → type=welcome, role=simulation_worker,
  worker_id, capabilities, authority_epoch, bot_authority_id, phase, round_id
```

## 4. 权威服务器 / sim-worker

### 4.1 Authority Worker 设计

`authority_worker.py` 是权威模拟进程的生命周期管理器：

```python
# authority_worker.py:3-8
"""Dedicated #1513 client lifecycle for native bot simulation authority.

The worker is not a player.  It keeps one private, off-map Avatar only because
the exact client exposes terrain, model nodes and hit testers through a loaded
native battle space.  That synthetic identity is projected into this process'
BattleRuntime messages and is never sent to the LAN server.
"""
```

**关键常量**：
```python
WORKER_ROLE = 'simulation_worker'
WORKER_MONITOR_SECONDS = 0.10   # 100ms 监控循环
WORKER_RETRY_SECONDS = 1.0      # 重试间隔
WORKER_BUSY_RETRY_SECONDS = 5.0 # 忙碌重试
WORKER_RETRY_MAX_SECONDS = 15.0 # 最大重试间隔
WORKER_DUMMY_Y = -500.0         # 地图外 dummy Avatar Y 坐标
```

### 4.2 Worker 工作流程

1. 启动完整游戏客户端进程（headless）
2. 通过 `instance_guard` 释放单实例限制
3. 隐藏所有窗口（私有 desktop）
4. 创建 dummy Avatar（地图外）
5. 连接 LAN 服务器，注册为 `simulation_worker`
6. 在 native 战斗空间运行 Bot/弹道/碰撞权威计算
7. 以 v5 协议发送 `bot_state`、`projectile_*` 等给服务器
8. 服务器 15 Hz 向可见客户端广播 replica 快照

### 4.3 服务器端常量

```python
# lan_battle_server.py:74-96
PROTOCOL_VERSION = 5
TICK_HZ = 30.0
BOT_PLANNER_INTERVAL_TICKS = max(1, int(round(TICK_HZ)))  # ~1Hz
REPLICA_SNAPSHOT_HZ = 15.0
BOT_MANIFEST_REFRESH_TICKS = max(1, int(round(TICK_HZ * 5.0)))
DESTRUCTIBLE_REFRESH_TICKS = max(1, int(round(TICK_HZ * 10.0)))
PREBATTLE_SECONDS = 10.0
BATTLE_DURATION_SECONDS = 900.0
MIN_BATTLE_DURATION_SECONDS = 60
MAX_BATTLE_DURATION_SECONDS = 14400
```

## 5. 薄客户端补丁

### 5.1 Wotmod 入口

```python
# mod_offline_lan_0922.py:1-9
from gui.mods.offline_lan_0922 import bootstrap

def init():
    bootstrap.init()

def fini():
    bootstrap.fini()
```

仅 9 行；所有逻辑在 `bootstrap` 与包内模块。

### 5.2 Bootstrap 初始化流程

```python
# bootstrap.py:1332-1369
def init():
    requested_mode = os.environ.get(port_config.CLIENT_MODE_ENV, '')
    _client_guard_released = instance_guard.release_if_requested()
    
    if requested_mode == port_config.SIMULATION_WORKER_MODE:
        if not _client_guard_released:
            # worker 启动被拒绝（多实例互斥未解开）
            ...
```

**player 模式**：
- 释放实例守卫（如果设置了环境变量）
- 装载公告抑制 + `LanSession` + pin 账户设置
- 伪造离线 Account 进入大厅

**worker 模式**：
- 释放实例守卫（必须成功）
- 只装 `WorkerSession`（连服务器、隐藏窗口、无车库 UI）
- 等待 TCP 就绪（welcome + connected + ready）

### 5.3 客户端连接流程

1. 读 `mods\configs\offline_lan_0922\server_endpoint.json` 或环境变量
2. `LANClient(host, port)` 后台线程 TCP 连接
3. 首包 `hello`（携带 `CLIENT_BUILD` + capabilities）
4. 服务器回 `welcome`（协议、role、round_id 等）
5. 大厅点击 Battle → `join` → 等待房间 → `request_start(map)` → 进战

## 6. 多实例限制处理（重点）

### 6.1 互斥体名

```c
// offline_instance_guard_native.c:57
#define CLIENT_MUTEX_NAME L"wot_client_mutex"

// offline_worker_starter.c:17
#define WORKER_MUTEX_NAME L"Local\\offline_lan_0922_worker"
```

### 6.2 Python 侧 instance_guard.py

```python
# instance_guard.py:7-9
ALLOW_MULTIPLE_CLIENTS_ENV = 'OFFLINE_LAN_0922_ALLOW_MULTIPLE_CLIENTS'
NATIVE_MODULE_NAME = 'offline_instance_guard_native'
GAME_VERSION_DIR = '0.9.22.0.1'
```

**工作流程**：
1. **opt-in**：仅当 `OFFLINE_LAN_0922_ALLOW_MULTIPLE_CLIENTS=1` 才尝试解除
2. **加载 sidecar**：`imp.load_dynamic('offline_instance_guard_native', <game>/mods/0.9.22.0.1/offline_instance_guard_native.pyd)`
3. **必须暴露**：`install_atmosphere_owner_guard`、`release_client_guard`、`hide_process_windows`、`show_process_windows`
4. **release_client_guard()**：调引擎自己的 WGC cleanup thunk
5. **hide/show_process_windows**：供 worker 隐藏顶层窗口

### 6.3 Native C 实现（offline_instance_guard_native.c，1400 行）

**硬编码 #1513 PE 身份**：

```c
#define EXPECTED_PE_TIMESTAMP 0x5a6edca4U
#define EXPECTED_IMAGE_BASE 0x00400000U
#define EXPECTED_IMAGE_SIZE 0x0206a000U

#define RVA_PY_INIT_MODULE4 0x00be1940U
#define RVA_PY_INT_FROM_LONG 0x00be1180U
#define RVA_WGC_CLEANUP_THUNK 0x004b7180U
#define RVA_WGC_HOLDER 0x019351ecU
#define RVA_WGC_WRAPPER_VTABLE 0x010ef788U
```

**release_client_guard 流程**（line 387-455）：

1. `holder = *(base + RVA_WGC_HOLDER)`
2. 校验 wrapper vtable、api(+0x44)、child(+0x48)、state(+0x50)
3. `cleanup = (WgcCleanupThunkFn)(base + RVA_WGC_CLEANUP_THUNK)`
4. `cleanup(holder)` — 调用引擎自己的完整 WGC 析构（释放 AppMutex）
5. 校验 api/child 清零、state==4
6. `verify_client_mutex_absent()` — `OpenMutexW` 查 `wot_client_mutex` 是否消失

**安全边界**：
- 只在验证过的 #1513 镜像上工作；签名不符则拒绝
- 不直接 `CloseHandle` WGC 句柄；只调引擎自己的 cleanup thunk
- mutex 检测用独立 probe handle，从不 `ReleaseMutex` 别人的句柄
- 磁盘文件从不被 patch（只改进程内存指令）

### 6.4 Worker 启动器（offline_worker_starter.c，1669 行）

- 无窗口启动客户端
- 必要时用**私有 desktop** 隐藏 `SW_SHOW` 的主 HWND
- Worker 互斥：`Local\\offline_lan_0922_worker`
- Ready marker 文件协议：`offline-worker.ready` / `.internal-ready` / `offline-player-%lu.ready`
- ProcDump 集成：崩溃转储采集
- Job 跟踪最多 32 个游戏进程

### 6.5 批处理启动脚本

```batch
REM START_SIMULATION_WORKER_0922.bat
set "OFFLINE_LAN_0922_CLIENT_MODE=simulation_worker"
set "OFFLINE_LAN_0922_ALLOW_MULTIPLE_CLIENTS=1"
start "" "%GAME_ROOT%offline_worker_starter.exe" --worker-only
```

## 7. 客户端预测与服务器校正

### 7.1 预测模型

| 角色 | 模型 |
|---|---|
| 本地玩家 | **客户端权威**：本地复制物理跑自己的坦克；每帧 `send_input` 到服务器；服务器不改本地姿态 |
| 远程车辆/Bot | **服务器/worker 权威 + 客户端插值/抖动缓冲**；仅确认样本内插，不做远端外推 |
| 弹道 | worker 权威 launch record（origin/velocity/gravity/lifetime）；客户端按同一抛物线呈现 |
| 可破坏物 | 客户端可本地 prediction，worker 终审 |

### 7.2 snapshot_sync.py 机制

**核心常量**：

```python
PREDICTION_SECONDS = 0.05          # 旧式速度外推上限
INITIAL_TIMED_DELAY_US = 90000.0   # 起步 jitter buffer 90ms
MIN_TIMED_DELAY_US = 60000.0       # 最小缓冲 60ms
TIMED_DELAY_GROW_STALL_US = 100000.0  # 生产者停顿立刻扩缓冲
TIMED_WARMUP_INTERVALS = 3
SNAP_DISTANCE = 25.0               # 瞬移阈值
MAX_VELOCITY = 80.0
```

**每渲染帧 advance()**：
1. 若有 ≥2 个 timed 样本：用 adaptive confirmed-history high-water mark 计算 `presentation_time_us`
2. **绝不外推超过最新确认样本**
3. 在样本间做位置/角度插值
4. 若无 timed 数据：速度外推 `predict = min(elapsed, PREDICTION_SECONDS)`
5. 远超阈值时 snap（`SNAP_DISTANCE = 25m`）

**本地玩家路径**：

```python
if local:
    record['current'] = dict(pose)
    self._emit({..., 'pose': pose, 'correction': True}, output)
```

local 实体不进入 timed 缓冲，直接吃权威快照作硬校正边界。

## 8. 房间 / 大厅 / 匹配 / 聊天 / 断线重连

### 8.1 大厅呈现（lobby_ui.py）

- 只抑制 ChinaController.onLobbyInited 自动浏览器
- 不替换 `showBrowser`、不禁用 `BrowserController`

### 8.2 匹配/队列屏

- **没有真正的 matchmaking**：固定房间制
- 服务器按 host 的 start 填满队伍至 `TEAM_SIZE`
- 使用 stock battle-queue screen

### 8.3 等待房间（waiting_room_ui.py）

- 用 BigWorld 原生 GUI（`GUI.Simple/Window/Text`）画覆盖层
- 显示玩家列表、Bot tier/skill、队伍容量
- START BATTLE / LEAVE 按钮

### 8.4 聊天（tactical_radio.py）

- 仅队伍频道；无全局/共同频道
- 团队文本/小地图 ping 中立后、死亡后仍可用
- 通过 `Avatar.messenger_onActionByServer_chat2` 回传

### 8.5 断线重连

```python
# lan_session.py:19-23
RECONNECT_DELAY = 2.0
ROUND_END_TIMEOUT = 12.0
```

- 等待房间掉线 → 提示 "LAN room connection lost. Click Battle! to rejoin."
- 战斗掉线 → 回车库；死后离场玩家重连可拿持久结果回执
- 轮结束后 12 秒未回等待房间则 rejoin

## 9. 启动与部署

### 9.1 批处理启动

| 文件 | 作用 |
|---|---|
| `START_OFFLINE_0922.bat` | 只启可见 player |
| `START_LAN_CLIENT_0922.bat` | 加入者：`offline_worker_starter.exe --player` |
| `START_SIMULATION_WORKER_0922.bat` | 设 worker 模式 + 多实例，`--worker-only` |

### 9.2 打包（build_wotmod.py）

```python
MOD_ID = 'org.peng.offline_lan_0922'
MOD_VERSION = '0.7.7'
NATIVE_BRIDGE_FILENAME = 'offline_instance_guard_native.pyd'
WORKER_STARTER_FILENAME = 'offline_worker_starter.exe'
PYTHON_MAGIC = '\x03\xf3\r\n'   # CPython 2.7
```

- 用 CPython 2.7 编译为 PYC
- 打成 `.wotmod`（ZIP_STORED）
- 部署到 `mods/0.9.22.0.1/`

### 9.3 启动器部署流程

`launcher/core.py` `install_client_mod`：
- 解压 bundle ZIP 到游戏根
- 事务式安装（staging + 原子替换）
- 只清 package 自己拥有的文件
- wotmod 路径：`mods/0.9.22.0.1/org.peng.offline_lan_0922*.wotmod`
- sidecar：`mods/0.9.22.0.1/offline_instance_guard_native.pyd`

## 10. 可复制 vs 需重写

### 10.1 版本无关 / 高可移植

| 模块 | 说明 |
|---|---|
| **LAN 协议语义**（v5 JSON） | hello/welcome/input/fire_intent/bot_state/projectile_ledger/destructible/rules_state |
| `server/lan_battle_server.py` 网络骨架 | socketserver TCP + JSON lines + 30Hz tick + 能力协商 |
| `windows_server.py` | 几乎纯部署（防火墙/环境变量） |
| `snapshot_sync.py` 大部分 | 纯数学插值/jitter buffer |
| 导航图数据格式、bake 工具 | 地图无关的离线烘焙流程 |
| 协议测试风格 | 可复用到任意版本的契约测试 |
| `launcher` 中的 save/shop 管理概念 | 产品层，与引擎无关 |

### 10.2 强依赖 0.9.22 / #1513 API

| 模块 | 依赖点 |
|---|---|
| **整个 `compat.py`** | 伪造 Account/ServerSettings/账户设置/dossier 等 |
| `authority_worker.py` | native battle space、Avatar 生命周期 |
| `battle_runtime.py` + `entities/*` | BigWorld entity/Avatar/Vehicle 呈现 ABI |
| `instance_guard` + **全部 native C** | 硬编码 PE timestamp、RVA、WGC 结构布局 |
| `lobby_ui` / `queue_*` / `waiting_room_ui` | ChinaController、prb_control、GUI.Simple/Flash |
| `tactical_radio` | `Avatar.messenger_onActionByServer_chat2`、action ID 表 |
| `build_wotmod.py` | PYC magic、`mods/0.9.22.0.1` 路径 |
| `vehicle_configuration` | #1513 items.vehicles 结构 |

### 10.3 移植结论

- **协议 + 服务器 tick/房间状态机可复用**
- **客户端侧几乎全部需要按新版本重写**（compat、entity 呈现、instance_guard RVA、UI hook）
- **native C 必须为 x64 重写**（0.9.22 是 32-bit，2.3.1.2 是 64-bit）

## 11. 测试覆盖

参考项目有 ~130 个测试文件，覆盖：
- 协议（`test_port_0922_lan_protocol.py`）
- 服务器（`test_port_0922_windows_server.py`）
- 战斗运行时（`test_port_0922_battle_runtime.py`）
- 实例守卫（`test_port_0922_instance_guard.py`、`test_port_0922_native_instance_guard.py`）
- 快照同步（`test_port_0922_snapshot_sync.py`）
- 各种战斗机制（ballistics、gun_mechanics、spotting 等）

## 12. 总结

### 12.1 可直接借鉴

1. **权威模型**：隐藏 worker 权威 + 可见客户端薄输入
2. **协议设计**：JSON lines + 能力协商 + 30Hz tick + 15Hz 快照
3. **预测哲学**：本地玩家本地物理；远程只确认样本插值
4. **多实例方案**：命名 mutex + 引擎 WGC cleanup thunk + 窗口隐藏
5. **部署方式**：.wotmod + sidecar pyd + 批处理启动

### 12.2 必须重写

1. **native C**：x64 版本（0.9.22 的 32-bit RVA 无法使用）
2. **compat.py**：2.3.1.2 的 Account/ServerSettings API
3. **entity 呈现**：2.3.1.2 的 BigWorld entity ABI
4. **UI hook**：2.3.1.2 的 GUI 系统
5. **descriptor 读取**：2.3.1.2 的 items.vehicles 结构
