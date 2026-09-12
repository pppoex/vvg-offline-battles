# 01 - Offline2.3.1.2 项目扫描报告

> 扫描时间：2026-09-12
> 扫描范围：`D:\Projects\Offline2.3.1.2`（只读）
> 游戏安装：`D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2`（经符号链接）

## 1. 项目概览

| 属性 | 值 | 证据 |
|---|---|---|
| 游戏版本 | v.2.3.1.2 #921 | `version.xml`: `<version> v.2.3.1.2 #921 </version>` |
| 客户端架构 | **64-bit x64** | `python.log`: `WorldOfTanks(x64) 2.3.1.10157 #2597749` |
| Python 版本 | **Python 2.7** | bytecode magic `62211`；`win64/python27.dll` 存在 |
| 反编译工具 | uncompyle6 3.9.3 | 所有 `.py` 文件头部注释 |
| 源文件数量 | 51 个 `.py` 文件 | `Get-ChildItem -Recurse -Filter *.py` |
| 总大小 | ~2.5 MB | 各文件 Length 之和 |
| Realm | EU | `version.xml`: `<realm> EU </realm>` |
| 分支 | v2.3.1 | `version.xml`: `<branch> v2.3.1 </branch>` |

## 2. 目录结构

```
D:\Projects\Offline2.3.1.2\
└── script\
    └── client\
        └── gui\
            └── mods\
                ├── mod_Map_selector_v120.py          (24 KB)
                ├── mod_offhangar2.py                 (8 KB)
                └── offhangar2\                       (核心包)
                    ├── __init__.py                   (7 KB)
                    ├── account_data.py               (77 KB)
                    ├── ai_tactics.py                 (16 KB)
                    ├── armour.py                     (23 KB)
                    ├── avoid_zones.py                (15 KB)
                    ├── badges.py                     (12 KB)
                    ├── battle.py                     (165 KB) ★
                    ├── battle_pass.py                (73 KB)
                    ├── battle_server.py              (5 KB)
                    ├── bots.py                       (95 KB)
                    ├── bot_routes.py                 (3 KB)
                    ├── capture.py                    (15 KB)
                    ├── config.py                     (39 KB)
                    ├── crewskills.py                 (6 KB)
                    ├── depot.py                      (6 KB)
                    ├── destructibles.py              (60 KB)
                    ├── diag.py                       (37 KB)
                    ├── drive.py                      (206 KB) ★
                    ├── edit_account.py               (2 KB)
                    ├── fake_server.py                (208 KB) ★
                    ├── friends.py                    (14 KB)
                    ├── hangar.py                     (98 KB)
                    ├── hooks.py                      (2 KB)
                    ├── intsettings.py                (5 KB)
                    ├── loadout.py                    (9 KB)
                    ├── log.py                        (3 KB)
                    ├── login.py                      (19 KB)
                    ├── lootboxes.py                  (56 KB)
                    ├── mechanics.py                  (243 KB) ★
                    ├── missions.py                   (24 KB)
                    ├── modes.py                      (27 KB)
                    ├── modules_crew.py               (64 KB)
                    ├── names.py                      (19 KB)
                    ├── platoon.py                    (22 KB)
                    ├── playtest_save.py              (4 KB)
                    ├── post_progression.py           (33 KB)
                    ├── premium_tree.py               (9 KB)
                    ├── recruits.py                   (46 KB)
                    ├── results.py                    (77 KB)
                    ├── server_settings.py            (11 KB)
                    ├── shooting.py                   (179 KB) ★
                    ├── shop.py                       (15 KB)
                    ├── shutdown.py                   (4 KB)
                    ├── spawn.py                      (76 KB)
                    ├── spotting.py                   (53 KB)
                    ├── store.py                      (46 KB)
                    ├── tank_collision.py             (25 KB)
                    ├── turret.py                     (92 KB)
                    ├── web_server.py                 (31 KB)
                    └── __init__.py                   (7 KB)
```

## 3. 入口与加载机制

### 3.1 入口文件

`mod_offhangar2.py`（8 KB）是 BigWorld mod 入口。游戏引擎加载 `res_mods/2.3.1.2/scripts/client/gui/mods/` 下的 `.py` 文件时自动执行。

`offhangar2/__init__.py` 中的 `install()` 函数是核心安装入口：

```python
# __init__.py (line 14-19)
VERSION = '2.0-offline'

def install():
    from gui.mods.offhangar2 import shutdown, login, battle, premium_tree, web_server, hangar, config, diag
    shutdown.install()
    login.install()
    battle.install()
    premium_tree.install()
    web_server.startShopServer()
    hangar.install()
```

### 3.2 Hook 系统

`hooks.py` 提供了方法替换装饰器：

```python
# hooks.py
def override(holder, name):
    def _decorator(replacement):
        original = getattr(holder, realName)
        def _wrapper(*args, **kwargs):
            return replacement(original, *args, **kwargs)
        setattr(holder, realName, _wrapper)
        return _wrapper
    return _decorator
```

### 3.3 加载路径

从 `python.log` 确认：

```
[PY_DEBUG] Checking D:/.../res_mods/2.3.1.2/: mods not found
[PY_DEBUG] Checking D:/.../mods/2.3.1.2/: mods not found
```

游戏检查两个位置：
1. `res_mods/2.3.1.2/` — 标准 mod 路径
2. `mods/2.3.1.2/` — 替代 mod 路径

当前 `res_mods/2.3.1.2/` 为空，mod 尚未部署。

## 4. 核心模块分析

### 4.1 fake_server.py (208 KB) — 假服务器

**用途**：模拟 BigWorld 服务器端的 Account 命令处理。

**核心类**：`FakeServer`

**关键功能**：
- 车库同步（`_cmdSyncData`）
- 商店同步（`_cmdSyncShop`）
- 档案同步（`_cmdSyncDossiers`）
- 购买车辆（`_cmdBuyVehicle`）
- 装备模块（`_cmdEquip`）
- 车组管理（`_cmdTmanAddSkill`, `_cmdEquipTman` 等）
- 技能训练（`_cmdTrainingTman`）
- 战斗队列（`_cmdEnqueueInBattleQueue`）

**证据**（fake_server.py line 731）：

```python
class FakeServer(object):
    # 模拟 BigWorld Account 服务器端命令处理
```

**联机改造影响**：此模块需要拆分——客户端部分保留（本地预览），服务器部分移至 sim-worker。

### 4.2 battle.py (165 KB) — 战斗生命周期

**用途**：管理战斗进入、离开、地图加载、生成、倒计时、结束。

**关键函数**：
- `enter(mapName)` / `enterRandom()` — 进入战斗
- `_createArena()` / `_createArenaAsBattleWorld()` — 创建竞技场
- `leave()` / `_finishLeave()` — 离开战斗
- `_spawnBots()` — 生成机器人
- `_startCountdown()` — 开始倒计时
- `_endBattle()` — 结束战斗
- `_watchBattleEnd()` — 监控战斗结束

**证据**（battle.py line 68）：

```python
def enter(mapName=None):
    # 进入战斗的入口函数
```

**联机改造影响**：需要重构为薄客户端逻辑——只保留渲染和 UI，战斗状态从 sim-worker 接收。

### 4.3 mechanics.py (243 KB) — 车辆机制模拟

**用途**：模拟各种车辆特殊机制（推进器、火箭、氮气加速、双炮等）。

**核心类**：
- `_FakePropellantCore` — 推进器
- `_FakeRocketCore` — 火箭
- `_FakeRechargeableNitroCore` — 可充电氮气
- `_FakeTwinGunCore` — 双炮
- `_FakeLowChargeCore` — 低装填
- `_FakeAutoShootCore` — 自动射击
- `_FakeOverheatCore` — 过热
- `_FakeTemperatureCore` — 温度
- `_FakeSupportWeaponCore` — 支援武器
- `_FakeChargeShotCore` — 蓄力射击
- `_FakeBattleFuryCore` — 战斗狂怒
- `_FakeExtraShotClipCore` — 额外弹夹
- `_FakeStationaryReloadCore` — 固定装填

**证据**（mechanics.py line 79）：

```python
class _FakePropellantCore(object):
    # 模拟推进器机制
```

**联机改造影响**：机制计算必须移至 sim-worker（服务器权威），客户端只保留视觉表现。

### 4.4 drive.py (206 KB) — 驾驶模拟

**用途**：车辆移动模拟，包括物理、碰撞、地形响应。

**核心类**：`_DriveState`

**证据**（drive.py line 24）：

```python
class _DriveState(object):
    def __init__(self, vehicle, position, yaw):
        self.controller = None
        self.vehicleID = vehicle.id
        self.spaceID = vehicle.spaceID
        self.position = position
        self.yaw = yaw
```

**联机改造影响**：移动权威必须移至 sim-worker，客户端保留预测和插值。

### 4.5 shooting.py (179 KB) — 射击机制

**用途**：弹道计算、命中判定、伤害应用、装甲效果。

**关键函数**：
- `_onVehicleShoot()` — 射击事件处理
- `_flyAndResolve()` — 弹道飞行与命中解析
- `_traceProjectile()` — 弹道追踪
- `applyDamage()` — 应用伤害
- `shellDamage()` — 计算炮弹伤害
- `_piercingMultiplier()` — 穿深系数

**证据**（shooting.py line 725）：

```python
def _flyAndResolve(avatar, vehicle, shotID, shot, shell, origin, velocity, damageFactor=1.0):
    # 弹道飞行与命中解析
```

**联机改造影响**：开火、命中、伤害计算全部移至 sim-worker。

### 4.6 battle_server.py (5 KB) — 战斗服务器桩

**用途**：拦截 Avatar/Vehicle 的 cell/base 属性，用 FakeCell 替代。

**证据**（battle_server.py line 42）：

```python
class FakeCell(object):
    def __getattr__(self, name):
        return _NoOp(name)
```

**联机改造影响**：此模块是单机模式的核心——需要替换为真正的网络连接到 sim-worker。

### 4.7 login.py (19 KB) — 离线会话管理

**用途**：创建离线会话，绕过真实服务器连接。

**关键机制**：

```python
# login.py line 63-78
def enterEngineOfflineMode():
    """通过 BigWorld.connect("") 创建空连接"""
    BigWorld.connect('', None, _onEngineOfflineProgress)
    # 连接后 BigWorld.serverTime() 返回有效值
```

**联机改造影响**：需要改为连接 sim-worker，或保留离线模式作为本地 sim-worker 的替代。

### 4.8 bots.py (95 KB) — 机器人 AI

**用途**：战斗中的机器人行为控制。

**联机改造影响**：机器人 AI 逻辑需要评估——如果在 sim-worker 上运行，客户端只需要渲染。

## 5. 依赖与导入分析

### 5.1 BigWorld 引擎依赖

所有核心模块都依赖 BigWorld 引擎：

```python
import BigWorld
import Math
from gui.mods.offhangar2 import config, hooks, log
```

关键 BigWorld API 使用：
- `BigWorld.connect()` — 连接服务器
- `BigWorld.callback()` — 延迟回调
- `BigWorld.entity()` — 获取实体
- `BigWorld.createEntity()` — 创建实体
- `BigWorld.serverTime()` — 服务器时间
- `BigWorld.time()` — 客户端时间
- `BigWorld.player()` — 获取玩家实体

### 5.2 游戏模块依赖

```python
import Avatar, Vehicle, Account, AccountCommands
import constants
from items import tankmen, vehicles
from CurrentVehicle import g_currentVehicle
from ArenaType import g_cache
```

### 5.3 标准库依赖

```python
import cPickle, zlib, json, os, sys, math, random, time, weakref, inspect
```

**Python 2 特征**：
- `cPickle`（Python 3 中为 `pickle`）
- `print` 语句（非函数）
- `dict.iteritems()`
- `unicode` / `basestring`
- `long` 类型

### 5.4 C 扩展依赖

从代码分析，**未发现直接的 C 扩展导入**。所有功能通过 Python 层实现。

但 BigWorld 引擎本身提供 C 扩展（`BigWorld` 模块是 C 扩展）。

## 6. 单机逻辑架构

### 6.1 核心模式

```
┌─────────────────────────────────────────────┐
│              游戏客户端 (x64)                │
│  ┌───────────────────────────────────────┐  │
│  │         BigWorld 引擎                  │  │
│  │  ┌─────────┐  ┌─────────┐  ┌───────┐ │  │
│  │  │ Avatar  │  │ Vehicle │  │ Space │ │  │
│  │  └────┬────┘  └────┬────┘  └───────┘ │  │
│  │       │            │                  │  │
│  │  ┌────▼────────────▼────┐            │  │
│  │  │   FakeCell (拦截)    │            │  │
│  │  └──────────┬───────────┘            │  │
│  └─────────────┼────────────────────────┘  │
│                │                            │
│  ┌─────────────▼────────────────────────┐  │
│  │        offhangar2 Mod                 │  │
│  │  ┌──────────┐ ┌──────────┐ ┌───────┐ │  │
│  │  │fake_server│ │ battle   │ │drive  │ │  │
│  │  └──────────┘ └──────────┘ └───────┘ │  │
│  │  ┌──────────┐ ┌──────────┐ ┌───────┐ │  │
│  │  │mechanics │ │ shooting │ │ bots  │ │  │
│  │  └──────────┘ └──────────┘ └───────┘ │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### 6.2 单机流程

1. 游戏启动 → 加载 `res_mods` 中的 mod
2. `offhangar2.install()` → 安装所有 hook
3. `login.install()` → 拦截登录流程
4. `enterEngineOfflineMode()` → `BigWorld.connect("")` 创建空连接
5. `battle_server.install()` → 将 Avatar/Vehicle 的 cell/base 替换为 FakeCell
6. `fake_server.FakeServer` → 响应所有 Account 命令
7. `battle.enter()` → 创建本地竞技场
8. `drive.py` / `mechanics.py` / `shooting.py` → 本地模拟所有游戏逻辑

## 7. 可复用模块评估

### 7.1 可直接复用（SDK 候选）

| 模块 | 大小 | 可复用性 | 说明 |
|---|---|---|---|
| `hooks.py` | 2 KB | ★★★★★ | 通用 hook 系统 |
| `log.py` | 3 KB | ★★★★★ | 日志系统 |
| `config.py` | 39 KB | ★★★★☆ | 配置管理（需适配） |
| `armour.py` | 23 KB | ★★★★☆ | 装甲计算（版本无关） |
| `tank_collision.py` | 25 KB | ★★★★☆ | 碰撞检测 |
| `intsettings.py` | 5 KB | ★★★★☆ | 整数设置 |
| `names.py` | 19 KB | ★★★☆☆ | 名称处理 |

### 7.2 需要重构（移至 sim-worker）

| 模块 | 大小 | 重构方向 | 说明 |
|---|---|---|---|
| `fake_server.py` | 208 KB | 拆分客户端/服务器 | 车库逻辑可保留，命令处理移至服务器 |
| `battle.py` | 165 KB | 拆分渲染/逻辑 | 渲染保留客户端，状态管理移至服务器 |
| `mechanics.py` | 243 KB | 逻辑移至服务器 | 机制计算必须服务器权威 |
| `drive.py` | 206 KB | 逻辑移至服务器 | 移动权威必须服务器决定 |
| `shooting.py` | 179 KB | 逻辑移至服务器 | 开火/命中/伤害必须服务器权威 |
| `bots.py` | 95 KB | 评估 | 如果机器人在服务器，客户端只渲染 |
| `turret.py` | 92 KB | 逻辑移至服务器 | 炮塔旋转权威 |
| `spotting.py` | 53 KB | 逻辑移至服务器 | 侦察逻辑 |
| `spawn.py` | 76 KB | 逻辑移至服务器 | 生成逻辑 |
| `capture.py` | 15 KB | 逻辑移至服务器 | 占领逻辑 |

### 7.3 客户端保留

| 模块 | 大小 | 说明 |
|---|---|---|
| `hangar.py` | 98 KB | 车库 UI |
| `results.py` | 77 KB | 战斗结果 UI |
| `battle_pass.py` | 73 KB | 战斗通行证 UI |
| `modules_crew.py` | 64 KB | 模块/车组 UI |
| `lootboxes.py` | 56 KB | 开箱 UI |
| `recruits.py` | 46 KB | 招募 UI |
| `store.py` | 46 KB | 商店 UI |
| `turret.py` | 92 KB | 炮塔渲染/瞄准 |
| `web_server.py` | 31 KB | Web 服务器（商店页面） |

## 8. 单实例限制分析

### 8.1 Python 层检测结果

在 `Offline2.3.1.2` 的所有 `.py` 文件中搜索：

```
搜索关键词：mutex, Mutex, instance, singleton, already running, FindWindow, CreateEvent, single.?instance
```

**结果**：**未发现任何单实例限制相关的代码**。

所有匹配都是 `isinstance()` 类型检查或 `dependency.instance()` 依赖注入，与进程单实例控制无关。

### 8.2 引擎层推断

单实例限制**不在 Python 层**，而在：

1. **BigWorld 引擎 C++ 层** — 引擎初始化时创建互斥体
2. **Wargaming Game Center (WGC)** — `wgc_api.dll` 可能包含单实例检查
3. **Windows 层** — 可能使用命名互斥体

### 8.3 游戏目录中的证据

```
D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\
├── win64\
│   ├── wgc_api.dll          (2.4 MB)
│   ├── wgcs_api.dll         (2.4 MB)
│   ├── wgc360_api.dll       (2.4 MB)
│   └── WorldOfTanks.exe     (77 MB)
├── mods\
│   └── temp\
│       ├── net.openwg.native\native_wg\openwg_native.pyd
│       ├── net.openwg.network\native_wg\openwg_network.pyd
│       └── net.openwg.native.hooks\native\openwg_native_hooks.dll
└── wgc_api.exe              (1.3 MB)
```

**关键发现**：
- `wgc_api.dll` / `wgcs_api.dll` / `wgc360_api.dll` — Wargaming Game Center API
- `python.log` 显示：`[WGC] (-2131886077) Running WGC instance is not found in the system`
- 已安装的 `openwg` 系列 mod 包含 native 扩展，可能与网络/实例控制相关

### 8.4 与 0.9.22 参考项目的对比

0.9.22 参考项目的实例守卫（`instance_guard.py`）：

```python
# 环境变量控制
ALLOW_MULTIPLE_CLIENTS_ENV = 'OFFLINE_LAN_0922_ALLOW_MULTIPLE_CLIENTS'

# 通过 native C 模块释放 WGC guard
def _release_native(native_bridge=None):
    status = int(native_bridge.release_client_guard())
```

native C 模块（`offline_instance_guard_native.c`）：

```c
#define CLIENT_MUTEX_NAME L"wot_client_mutex"
#define RVA_WGC_CLEANUP_THUNK 0x004b7180U
#define RVA_WGC_HOLDER 0x019351ecU
```

**关键差异**：0.9.22 使用硬编码的 32-bit RVA，2.3.1.2 是 x64，**无法直接复用**。

## 9. 部署机制

### 9.1 当前部署状态

```
res_mods/2.3.1.2/  → 空（mod 未部署）
mods/2.3.1.2/      → 空
mods/temp/          → 已有 openwg 系列 mod
```

### 9.2 部署路径

游戏加载顺序（从 python.log 推断）：

1. 检查 `res_mods/2.3.1.2/`
2. 检查 `mods/2.3.1.2/`
3. 加载 `mods/temp/` 中的 mod

### 9.3 pyc 编译

当前源码是 `.py` 格式（反编译得到）。部署时需要：

1. 使用 Python 2.7 编译为 `.pyc`
2. 放置到 `res_mods/2.3.1.2/scripts/client/gui/mods/`

**注意**：游戏嵌入的 Python 2.7 可能对 `.pyc` magic number 有特定要求。需要验证。

## 10. 代码质量评估

### 10.1 反编译质量

- **整体质量**：良好
- **语法错误**：未发现明显的语法错误
- **混淆**：未发现混淆痕迹
- **缺失模块**：未发现缺失的 import
- **注释**：保留了大量原始注释（含英文技术说明）

### 10.2 特殊情况

`hooks.py` 中有一处反编译伪代码：

```python
# hooks.py line 48-49
        except Exception:
            (None, None)
            (None, None)
```

这是 uncompyle6 对 try/except 的反编译问题，实际应为：

```python
        except Exception:
            log.exc(...)
            return replacement
```

### 10.3 代码规模

| 类别 | 文件数 | 总大小 |
|---|---|---|
| 核心逻辑（>100 KB） | 5 | ~1.0 MB |
| 中等模块（10-100 KB） | 20 | ~1.2 MB |
| 小模块（<10 KB） | 26 | ~0.3 MB |
| **总计** | **51** | **~2.5 MB** |

## 11. 联机改造可行性评估

### 11.1 Python 层改造可行性

**结论：部分可行，但存在重大限制。**

**可行部分**：
- 车库/账户管理逻辑可复用
- UI 层可复用
- Hook 系统可复用
- 配置系统可复用

**不可行/高风险部分**：
- `battle_server.py` 的 FakeCell 拦截机制需要完全重写
- `mechanics.py` / `drive.py` / `shooting.py` 的本地模拟需要移至服务器
- `login.py` 的离线模式需要改为网络连接
- 大型模块（200+ KB）需要拆分

### 11.2 需要的额外手段

| 手段 | 用途 | 优先级 |
|---|---|---|
| 网络层 | 客户端-服务器通信 | **必须** |
| 协议定义 | 消息序列化 | **必须** |
| sim-worker | 权威服务器 | **必须** |
| 多实例解除 | 允许多客户端 | **必须** |
| 部署脚本 | 自动部署到 res_mods | **必须** |
| 启动器 | 命令行启动 | **必须** |
| 断线重连 | 网络断开恢复 | **必须** |

### 11.3 Python 库选型建议

| 需求 | 推荐库 | 版本 | 许可证 | Py2/Py3 | Windows |
|---|---|---|---|---|---|
| 网络（客户端） | `socket` + `json` | 标准库 | PSF | ✓ | ✓ |
| 网络（服务器） | `asyncio` | 3.4+ | PSF | ✗ (Py3) | ✓ |
| 网络（服务器备选） | `twisted` | 20.3+ | MIT | ✓ | ✓ |
| 进程管理 | `psutil` | 5.9+ | BSD | ✓ | ✓ |
| Windows API | `ctypes` | 标准库 | PSF | ✓ | ✓ |
| Windows API（增强） | `pywin32` | 306+ | PSF | ✓ | ✓ |
| 序列化（高效） | `msgpack` | 1.0+ | Apache-2.0 | ✓ | ✓ |
| 序列化（可读） | `json` | 标准库 | PSF | ✓ | ✓ |
| 测试 | `pytest` | 7.0+ | MIT | ✓ | ✓ |
| 日志 | `logging` | 标准库 | PSF | ✓ | ✓ |

## 12. 结论

### 12.1 Offline2.3.1.2 状态

- ✅ Python 2.7 代码，反编译质量良好
- ✅ 完整的单机模式实现
- ✅ 车库/账户/商店/战斗全流程覆盖
- ✅ 大量可复用的 UI 和配置代码
- ⚠️ 核心游戏逻辑（移动/射击/机制）在客户端本地模拟
- ❌ 无网络层
- ❌ 无多实例支持
- ❌ 大型模块需要拆分

### 12.2 联机改造路径

1. **抽取 SDK**：从 Offline2.3.1.2 抽取可复用模块
2. **构建协议**：定义客户端-服务器消息协议
3. **构建 sim-worker**：实现权威服务器
4. **改造客户端**：将本地模拟替换为网络通信
5. **解决多实例**：实现 x64 版本的实例守卫
6. **部署脚本**：自动化部署到 res_mods

### 12.3 风险标记

| 风险 | 等级 | 说明 |
|---|---|---|
| x64 实例守卫 | **高** | 0.9.22 方案无法直接使用 |
| BigWorld API 差异 | **中** | 2.3.1.2 API 可能与 0.9.22 不同 |
| Python 2.7 限制 | **中** | 客户端必须使用 Py2，服务器可用 Py3 |
| 模块拆分复杂度 | **中** | 大型模块需要仔细重构 |
| WGC 依赖 | **中** | Wargaming Game Center 可能影响联机 |
