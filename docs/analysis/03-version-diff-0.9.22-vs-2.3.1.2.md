# 03 - 版本差异分析：0.9.22 vs 2.3.1.2

> 分析时间：2026-09-12
> 对比对象：坦克世界 0.9.22.0.1 #1513（参考项目） vs 2.3.1.2 #921（目标项目）

## 1. 客户端架构差异

| 维度 | 0.9.22.0.1 #1513 | 2.3.1.2 #921 | 影响 |
|---|---|---|---|
| **CPU 架构** | 32-bit x86 | **64-bit x64** | **重大**：所有 native 代码必须重写 |
| **可执行文件** | `WorldOfTanks.exe`（x86） | `win64/WorldOfTanks.exe`（x64） | 路径不同 |
| **Python DLL** | 内嵌在 exe 中 | `win64/python27.dll`（5.6 MB） | 加载方式不同 |
| **PE Image Base** | `0x00400000` | 需要重新验证 | RVA 全部失效 |
| **PE Image Size** | `0x0206a000` | 需要重新验证 | RVA 全部失效 |
| **PE Timestamp** | `0x5a6edca4` | 需要重新验证 | 构建校验失效 |

### 证据

**0.9.22**：
```
COMPATIBILITY_REVIEW.md: "The executable is 32-bit x86"
offline_instance_guard_native.c: EXPECTED_IMAGE_BASE 0x00400000U
```

**2.3.1.2**：
```
python.log: "WorldOfTanks(x64) 2.3.1.10157 #2597749"
win64/python27.dll: 5589336 bytes
version.xml: <version> v.2.3.1.2 #921 </version>
```

## 2. Python 版本差异

| 维度 | 0.9.22 | 2.3.1.2 | 影响 |
|---|---|---|---|
| **Python 版本** | 2.7.7 | 2.7（具体小版本待验证） | 基本兼容 |
| **Bytecode Magic** | `03 f3 0d 0a` | `62211`（0x7203） | 相同（都是 Py2.7） |
| **反编译器** | — | uncompyle6 3.9.3 / Decompyle++ | — |

### 证据

**0.9.22**：
```
COMPATIBILITY_REVIEW.md: "Packaged client modules use CPython 2.7 bytecode magic 03 f3 0d 0a"
COMPATIBILITY_REVIEW.md: "The embedded build identifies itself as Python 2.7.7"
```

**2.3.1.2**：
```
所有 .py 文件头: "# Python bytecode version base 2.7 (62211)"
win64/python27.dll 存在
```

**结论**：Python 版本基本兼容（都是 2.7），但 .pyc magic number 可能不同（`03 f3 0d 0a` vs `62211`）。部署时需要用目标客户端的 Python 编译。

## 3. Wargaming Game Center (WGC) 差异

| 维度 | 0.9.22 | 2.3.1.2 | 影响 |
|---|---|---|---|
| **WGC 依赖** | 有（wgc_api.dll） | **有**（wgc_api.dll, wgcs_api.dll, wgc360_api.dll） | 单实例机制可能类似 |
| **WGC 版本** | 旧版 | **新版**（三个 DLL） | 结构布局可能不同 |
| **互斥体名** | `wot_client_mutex` | **待验证** | 需要逆向确认 |
| **WGC cleanup thunk** | RVA `0x004b7180` | **待验证** | 需要逆向确认 |

### 证据

**0.9.22**：
```c
// offline_instance_guard_native.c
#define CLIENT_MUTEX_NAME L"wot_client_mutex"
#define RVA_WGC_CLEANUP_THUNK 0x004b7180U
#define RVA_WGC_HOLDER 0x019351ecU
```

**2.3.1.2**：
```
win64/wgc_api.dll: 2398936 bytes
win64/wgcs_api.dll: 2404568 bytes
win64/wgc360_api.dll: 2397912 bytes
python.log: "[WGC] (-2131886077) Running WGC instance is not found in the system"
```

**关键发现**：2.3.1.2 有**三个** WGC DLL（0.9.22 可能只有一个），说明 WGC 架构有重大变化。

## 4. BigWorld API 差异

### 4.1 实体系统

| 维度 | 0.9.22 | 2.3.1.2 | 影响 |
|---|---|---|---|
| **Avatar 模块** | `Avatar.py` | `Avatar.py`（待验证 API） | 可能有变化 |
| **Vehicle 模块** | `Vehicle.py` | `Vehicle.py`（待验证 API） | 可能有变化 |
| **Account 模块** | `Account.py` | `Account.py`（待验证 API） | 可能有变化 |
| **Entity 创建** | `BigWorld.createEntity` | `BigWorld.createEntity`（待验证） | 基本兼容 |
| **Space 系统** | `BigWorld.addSpaceGeometryMapping` | `BigWorld.addSpaceGeometryMapping`（待验证） | 基本兼容 |

### 4.2 2.3.1.2 新增 API（从 Offline2.3.1.2 代码推断）

```python
# mechanics.py - 2.x 载具机制系统
from vehicles.mechanics import ...  # 机制组件系统
class _FakePropellantCore(object): ...  # 推进器
class _FakeRocketCore(object): ...  # 火箭
class _FakeRechargeableNitroCore(object): ...  # 可充电氮气
class _FakeTwinGunCore(object): ...  # 双炮
# ... 更多机制

# battle.py - 新 UI 系统
from gui.Scaleform.framework import ...  # Scaleform UI
from frameworks.state_machine.machine import ...  # 状态机

# config.py - dict2model
from dict2model import fields as F  # 数据模型
```

**结论**：2.3.1.2 引入了大量新 API 和机制系统，0.9.22 的代码无法直接使用。

### 4.3 载具机制系统差异

**0.9.22**：简单的伤害/击穿/模块损坏模型

**2.3.1.2**：复杂的机制组件系统
- 推进器（Propellant）
- 火箭（Rocket）
- 可充电氮气（Rechargeable Nitro）
- 双炮（Twin Gun）
- 低装填（Low Charge）
- 自动射击（Auto Shoot）
- 过热（Overheat）
- 温度（Temperature）
- 支援武器（Support Weapon）
- 蓄力射击（Charge Shot）
- 战斗狂怒（Battle Fury）
- 额外弹夹（Extra Shot Clip）
- 固定装填（Stationary Reload）

**影响**：mechanics.py（243 KB）的机制系统需要完整移植到 sim-worker。

## 5. 网络协议差异

| 维度 | 0.9.22 | 2.3.1.2 | 影响 |
|---|---|---|---|
| **BigWorld 协议** | 旧版 | **新版**（待逆向） | 无法直接复用 |
| **自有协议** | JSON lines v5 | 需要设计 | 需要重新设计 |
| **Account 命令** | `AccountCommands` 常量 | `AccountCommands` 常量（待验证） | 可能有变化 |

### 证据

**0.9.22**：
```python
# lan_client.py
PROTOCOL_VERSION = 5
CLIENT_BUILD = 'wot-0.9.22.0.1-cn-1513'
```

**2.3.1.2**：
```python
# fake_server.py - 大量 Account 命令处理
_cmdSyncData, _cmdSyncShop, _cmdBuyVehicle, _cmdEquip, ...
```

**结论**：BigWorld 原生协议无法复用，需要设计自己的协议。Account 命令集可能有变化，需要从 fake_server.py 提取。

## 6. 客户端启动和 mod 加载差异

### 6.1 加载路径

| 维度 | 0.9.22 | 2.3.1.2 | 影响 |
|---|---|---|---|
| **res_mods 路径** | `res_mods/0.9.22.0.1/` | `res_mods/2.3.1.2/` | 路径不同 |
| **mods 路径** | `mods/0.9.22.0.1/` | `mods/2.3.1.2/` | 路径不同 |
| **wotmod 支持** | 支持 | 支持（待验证） | 需要验证 |
| **配置路径** | `mods/configs/offline_lan_0922/` | 需要设计 | 需要设计 |

### 证据

**0.9.22**：
```
INSTALL.txt: mods\0.9.22.0.1\org.peng.offline_lan_0922_<version>.wotmod
```

**2.3.1.2**：
```
python.log: "Checking D:/.../res_mods/2.3.1.2/: mods not found"
python.log: "Checking D:/.../mods/2.3.1.2/: mods not found"
```

### 6.2 已安装的 Mod

**2.3.1.2** 已有 openwg 系列 mod：

```
mods/temp/
├── net.openwg.audio/native_wg/openwg_audio.pyd
├── net.openwg.filewatcher/native_wg/openwg_filewatcher.pyd
├── net.openwg.fonts/native_wg/openwg_fonts.pyd
├── net.openwg.native/native_wg/openwg_native.pyd
├── net.openwg.native.hooks/native/openwg_native_hooks.dll
└── net.openwg.network/native_wg/openwg_network.pyd
```

**影响**：需要确认这些 mod 是否与我们的 mod 冲突，以及是否提供了有用的 API。

## 7. 资源格式差异

| 维度 | 0.9.22 | 2.3.1.2 | 影响 |
|---|---|---|---|
| **地图格式** | 待验证 | 待验证 | 导航图需要重新烘焙 |
| **车辆描述符** | `items.vehicles` | `items.vehicles`（结构可能变化） | 需要重新读取 |
| **UI 资源** | Scaleform SWF | Scaleform SWF（版本可能变化） | UI hook 需要调整 |
| **字体** | `.font` | `.font`（待验证） | 基本兼容 |

## 8. 输入/相机/UI 差异

### 8.1 UI 系统

**0.9.22**：
```python
from gui.Scaleform.framework import ...
from gui import SystemMessages
from CurrentVehicle import g_currentVehicle
```

**2.3.1.2**（从 Offline2.3.1.2 推断）：
```python
from gui.Scaleform.framework import ...
from gui.Scaleform.genConsts import ...
from frameworks.state_machine.machine import ...
from helpers.dependency import ...
from skeletons.gui import ...
# 更多新 API
```

**影响**：UI hook 需要针对 2.3.1.2 重写。

### 8.2 相机系统

**0.9.22**：
```python
# 大厅相机
hangarSpace = dependency.instance(IHangarSpace)
```

**2.3.1.2**：
```python
# 可能有变化
FovExtended.instance().setFovByMultiplier(...)
```

**影响**：相机控制需要重新适配。

## 9. 物理/命中判定差异

### 9.1 物理引擎

| 维度 | 0.9.22 | 2.3.1.2 | 影响 |
|---|---|---|---|
| **物理引擎** | Havok | Havok（版本可能变化） | API 可能变化 |
| **碰撞检测** | BigWorld 内置 | BigWorld 内置 | 基本兼容 |
| **车辆物理** | 简单模型 | 可能更复杂 | drive.py 需要适配 |

### 9.2 命中判定

**0.9.22**：
```python
# 简单的弹道追踪
def _traceProjectile(...): ...
def applyDamage(...): ...
```

**2.3.1.2**：
```python
# 更复杂的命中判定（从 shooting.py 推断）
def _flyAndResolve(...): ...
def _traceProjectile(...): ...
def applyDamage(...): ...
def _piercingMultiplier(...): ...
# 更多细节
```

**影响**：命中判定逻辑需要移植到 sim-worker，并适配 2.3.1.2 的 API。

## 10. 多实例限制机制差异

| 维度 | 0.9.22 | 2.3.1.2 | 影响 |
|---|---|---|---|
| **互斥体** | `wot_client_mutex` | **待验证** | 需要逆向 |
| **WGC 结构** | 32-bit RVA | 64-bit RVA | **必须重写** |
| **窗口隐藏** | 私有 desktop | 私有 desktop（待验证） | 可能复用 |
| **环境变量** | `OFFLINE_LAN_0922_ALLOW_MULTIPLE_CLIENTS` | 需要设计 | 需要设计 |

### 关键差异

0.9.22 的 native 实例守卫使用**硬编码 32-bit RVA**：

```c
#define EXPECTED_IMAGE_BASE 0x00400000U
#define RVA_WGC_CLEANUP_THUNK 0x004b7180U
#define RVA_WGC_HOLDER 0x019351ecU
```

2.3.1.2 是 **64-bit x64**，所有 RVA 必须重新逆向。

**结论**：多实例守卫的 native C 必须完全重写。

## 11. 会导致参考项目代码无法直接使用的差异

### 11.1 必须重写的部分

| 组件 | 原因 | 工作量估计 |
|---|---|---|
| **native C (instance_guard)** | 32-bit → 64-bit，RVA 全部失效 | **高** |
| **native C (worker_starter)** | 架构变化 | **中** |
| **compat.py** | 2.3.1.2 API 变化 | **高** |
| **entity 呈现** | BigWorld entity ABI 变化 | **高** |
| **UI hook** | GUI 系统变化 | **高** |
| **descriptor 读取** | items.vehicles 结构变化 | **中** |
| **mechanics 系统** | 2.x 新机制系统 | **高** |

### 11.2 可以复用的部分

| 组件 | 原因 | 复用度 |
|---|---|---|
| **协议语义** | JSON lines + 能力协商 | **高** |
| **服务器骨架** | socketserver + tick 循环 | **高** |
| **snapshot_sync** | 纯数学插值 | **高** |
| **预测哲学** | 本地物理 + 确认样本插值 | **高** |
| **房间管理** | 等待房间 + 队伍分配 | **中** |
| **断线重连** | 重连逻辑 | **中** |

## 12. 适配风险评估

| 风险 | 等级 | 说明 | 缓解措施 |
|---|---|---|---|
| **x64 native 重写** | **高** | 需要逆向 2.3.1.2 的 WGC 结构 | 逆向分析 + 逐步验证 |
| **BigWorld API 变化** | **中** | 可能有不兼容的 API 变化 | 从 Offline2.3.1.2 提取 API 用法 |
| **机制系统复杂度** | **中** | 2.x 机制系统庞大 | 分模块移植 |
| **WGC 结构未知** | **高** | 2.3.1.2 的 WGC 结构未逆向 | 需要专门的逆向任务 |
| **互斥体名未知** | **中** | 不确定 2.3.1.2 的互斥体名 | 运行时探测 |
| **Python .pyc magic** | **低** | 可能与 0.9.22 不同 | 用目标客户端的 Python 编译 |

## 13. 结论

### 13.1 版本差异总结

1. **架构变化**：32-bit → 64-bit，这是最大的变化
2. **Python 兼容**：都是 2.7，基本兼容
3. **WGC 变化**：三个 DLL，结构可能完全不同
4. **API 变化**：大量新 API，特别是载具机制系统
5. **UI 变化**：Scaleform 版本可能变化

### 13.2 移植策略

1. **协议层**：复用 JSON lines 协议设计，适配 2.3.1.2 的数据格式
2. **服务器**：复用 socketserver + tick 架构，适配 2.3.1.2 的战斗逻辑
3. **客户端**：从 Offline2.3.1.2 提取 API 用法，重写 hook 和呈现
4. **native**：完全重写为 x64，需要专门的逆向任务
5. **机制系统**：从 Offline2.3.1.2 的 mechanics.py 移植到 sim-worker

### 13.3 关键待验证项

1. 2.3.1.2 的 WGC 互斥体名
2. 2.3.1.2 的 WGC cleanup thunk RVA
3. 2.3.1.2 的 Python .pyc magic number
4. 2.3.1.2 的 BigWorld entity ABI 具体变化
5. openwg 系列 mod 是否提供有用的 API
