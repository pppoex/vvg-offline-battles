# 多开 "already running" 深度调试报告

> TASK-M0.3 — 2026-09-12

## 结论

**根因**：mod 已被 BigWorld 正常加载，但 `instance_guard.py` 通过 `ctypes.CDLL` 加载 native pyd 时失败：

```text
[VVG instance guard] init mode=player allow_multi=1
[VVG instance guard] release failed: No module named _ctypes
[VVG instance guard] client guard release error: No module named _ctypes
```

WoT 2.3.1.2 内嵌 Python 2.7 **不提供** `_ctypes` 扩展模块（与 `D:\Python27` 不同），因此 `import ctypes` 在游戏内必败。

**修复**：改为优先用 `imp.load_dynamic` 把 `vvg_instance_guard_native.pyd` 作为 Python C 扩展模块直接导入（pyd 已导出 `initvvg_instance_guard_native`），完全绕过 ctypes。

## 证据时间线

| 时间 | 日志 | 含义 |
|---|---|---|
| 21:05 | `Checking .../res_mods/2.3.1.2/: mods not found` | 首次运行时 mod 尚未部署 |
| 21:15 | `mods found` | 部署后路径被识别 |
| 21:20:42 | `[VVG instance guard] init mode=player allow_multi=1` | **mod 入口已加载，环境变量正确** |
| 21:20:42 | `release failed: No module named _ctypes` | **失败点：无 _ctypes** |
| 21:20:49 | `fini` | 客户端退出时清理 |

关键路径：

- 玩家日志：`D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\vvg-player-python.log`
- 无 `python.log`（starter 用 `--logFilePrefix` 重定向到 vvg-*-python.log）

## 逐步诊断记录

### 1. 游戏日志

- `python.log` 不存在；实际日志为 `vvg-player-python.log` / `vvg-worker-python.log`
- 搜索 `vvg|instance_guard|mods`：mod **已加载**
- 错误仅 `No module named _ctypes`

### 2. Offline2.3.1.2 mod 机制

`mod_offhangar2.py` 使用标准 BigWorld 约定：

```python
def init():
    ...

def fini():
    ...
```

入口文件以 `mod_` 开头，位于 `res_mods/<ver>/scripts/client/gui/mods/`。

### 3. 参考项目 0.9.22

`mod_offline_lan_0922.py` 结构相同，委托 `bootstrap.init()`。

### 4. 当前实现

- 入口签名正确（`init`/`fini`）
- 包路径 `gui.mods.vvg_instance_guard` 正确
- **失败点在 `instance_guard._load_native_bridge` → `ctypes.CDLL`**

### 5–8. 加载路径 / 命名

- 游戏确认：`Checking .../res_mods/2.3.1.2/: mods found`
- pyc magic = `03 f3 0d 0a` (62211) 正确
- 文件命名与 Offline / 参考项目一致

### 9. 关键环境差异

| 环境 | `_ctypes` |
|---|---|
| `D:\Python27`（系统） | 有 |
| `D:\WOT\...\win64\python27.dll`（游戏内嵌） | **无** |

单测在系统 Python 下通过，掩盖了游戏内嵌环境缺少 `_ctypes` 的问题。

## 修复内容

### A. `src/multiclient/instance_guard.py`

1. 新增 `_has_ctypes()` / `_try_load_extension()` / `_ExtensionBridge`
2. `_load_native_bridge` 顺序：
   1. `imp.load_dynamic('vvg_instance_guard_native', path)` — **游戏内主路径**
   2. 回退 `ctypes.CDLL` — 仅当宿主有 `_ctypes`（单测）
   3. 两者都失败 → 带诊断信息的 `ImportError`

### B. `src/multiclient/native/instance_guard.c`

1. `vvg_init_bridge`：先解析 `PyInt_FromLong`，再做 host PE 校验 — 保证非游戏宿主下扩展方法也能返回 PyInt
2. `python_int`：必要时按需解析 `PyInt_FromLong`
3. `initvvg_instance_guard_native`：始终注册模块方法（不再在 host 失败时静默 return）
4. 暴露 Python 方法：`validate_host` / `init_bridge`

### C. `src/client/vvg_instance_guard/bootstrap.py`

增加诊断日志：

- `mod entry loaded mode=... allow_multi=...`
- 三个 `VVG_*` 环境变量
- `ctypes/_ctypes available=0|1`
- native path + exists
- 实际 loader（`extension` / `ctypes`）

## 验证步骤（用户）

1. 完全退出所有 WoT 进程
2. 用 `vvg_worker_starter.exe --player` 开第一个客户端到登录界面
3. 再开第二个 `vvg_worker_starter.exe --player`
4. 确认无 "already running" 弹窗
5. 检查 `vvg-player-python.log` / `vvg-worker-python.log` 应出现：

```text
[VVG instance guard] mod entry loaded mode=player allow_multi=1
[VVG instance guard] ctypes/_ctypes available=0
[VVG instance guard] native bridge path=... exists=1
[VVG instance guard] native bridge loaded via=extension
[VVG instance guard] released startup/WGC mutexes for multi-client
```

若仍有问题：

```powershell
Select-String -Path "D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\vvg-*.log" -Pattern "VVG"
```

## 残留风险

1. 互斥体名若非 `WOT_STARTUP_MUTEX` 候选列表中的名字，释放会返回 status 19/16 — 日志会显示
2. 句柄枚举方式与 0.9.22 引擎 cleanup thunk 不同，需真机确认
3. `atmosphere` owner guard 在 2.3.1.2 仍为 status 22（未映射）

## 已部署产物

| 路径 | 说明 |
|---|---|
| `res_mods/2.3.1.2/scripts/client/gui/mods/mod_vvg_instance_guard.py[c]` | 入口 |
| `res_mods/2.3.1.2/scripts/client/gui/mods/vvg_instance_guard/*.py[c]` | 包（含修复后的 instance_guard / bootstrap） |
| `mods/2.3.1.2/vvg_instance_guard_native.pyd` | native（重建） |
| `win64/vvg_instance_guard_native.pyd` | 同上副本 |
| `win64/vvg_worker_starter.exe` | 启动器（重建） |

## 测试

Python 2.7 下 `tests/unit`：**27/27 通过**（含新增 ExtensionLoader / extension-preferred 用例）。
