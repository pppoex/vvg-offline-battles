# 08 — 多实例限制解除逆向分析报告（2.3.1.2 x64）

> 分析时间：2026-09-12  
> 目标：`D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\win64`  
> 参考：0.9.22 #1513 的 `offline_instance_guard_native` 方案  
> 状态：M0 可编译实现已落地；部分运行时结构标记为**待验证**

## 1. PE 身份（已测量）

### 1.1 WorldOfTanks.exe

| 字段 | 值 |
|---|---|
| Machine | `0x8664` (x64) |
| TimeDateStamp | `0x6A759054` |
| ImageBase | `0x0000000140000000` |
| SizeOfImage | `0x0509F000` |
| Subsystem | 2 (GUI) |
| PE Magic | PE32+ |
| 文件大小 | 77,263,144 bytes |

### 1.2 wgc_api.dll

| 字段 | 值 |
|---|---|
| Machine | `0x8664` |
| TimeDateStamp | `0x62E3F741` |
| ImageBase | `0x0000000180000000` |
| SizeOfImage | `0x00251000` |
| 备注 | NA/360 变体：`wgcs_api.dll` / `wgc360_api.dll` 同构 |

### 1.3 python27.dll（关键差异）

| 字段 | 值 |
|---|---|
| Machine | `0x8664` |
| TimeDateStamp | `0x678A5608` |
| ImageBase | `0x180000000` |
| SizeOfImage | `0x579000` |
| 导出 | 完整 CPython 2.7 API，含 `Py_InitModule4_64`、`PyInt_FromLong`、`PyCapsule_*` |

**结论**：2.3.1.2 不再依赖 exe 内嵌解释器 RVA 定位 Python C API。native 扩展可通过 `GetProcAddress(python27.dll, ...)` 解析符号，兼容性显著优于 0.9.22 的硬编码 RVA。

## 2. 与 0.9.22 的机制差异

| 项目 | 0.9.22 #1513 | 2.3.1.2 #921 |
|---|---|---|
| 架构 | x86 32-bit | x64 |
| Python C API | exe RVA（`PyInitModule4` / `PyInt_FromLong`） | 独立 `python27.dll` 导出 |
| 主互斥体 | `wot_client_mutex` | **`WOT_STARTUP_MUTEX`**（`app.cpp`）+ WGC AppMutex |
| WGC cleanup | 引擎 thunk RVA `0x004b7180` | **未定位 cleanup thunk（待验证）** |
| 离线 WGC 行为 | 由离线栈控制 | `python.log`: `[WGC] (-2131886077) Running WGC instance is not found in the system`（软失败） |

## 3. 互斥体 / 单实例证据

### 3.1 主 exe

- UTF-16 字符串 `WOT_STARTUP_MUTEX` 紧邻 ASCII `RELEASE` 与路径片段 `ent\client\app.cpp`。
- **注意**：早期扫描误报为 `EWOT_STARTUP_MUTEX`，其中 `E` 来自相邻的 `RELEASE` 尾字节。
- 另有 UTF-16 孤立字符串 `wot_client`（可能是产品名片段，不一定是完整互斥体名）。
- 导入表含 `CreateMutexW` / `OpenMutexA` / `CreateMutexA` / `ReleaseMutex`。
- **不**从 `wgc*.dll` 静态导入；WGC 通过字符串 `WGCApiCreateInstance` / `WGCApiGetResultDescription` 动态绑定。
- WGC 集成源路径痕迹：`wgcore_integration_bwt.cpp`。
- 类型信息：`.?AVWGCControllerImpl@WGC@@`；日志串 `WGCControllerImpl::prepare: WGC API is not initialized`。

### 3.2 wgc_api.dll（AppMutex）

ASCII：

- `AppMutexError`, `app_mutex.cpp`, `win32\app_mutex_win32.cpp`
- `Ipc::AppMutexWin32::AppMutexWin32`, `Ipc::AppMutexWin32::isAppActive`
- `Failed to create app mutex`
- 导入：`CreateMutexW`, `OpenMutexW`

UTF-16 名称前缀：

- `wgc_game_mtx_`
- `wgc_running_games_mtx`
- `wgcs_running_games_mtx` / `wgc360_running_games_mtx`（变体 DLL）

用户可见文案：

- `The game is already running. You can continue the current game session or close it.`
- `Another game is running. To launch this game, first close the running one.`

### 3.3 运行时（python.log）

离线安装反复出现：

```text
[WGC] (-2131886077) Running WGC instance is not found in the system
```

说明本离线环境**没有常驻 WGC 进程**；WGC AppMutex 可能未创建或创建失败后降级。因此 **主闸门更可能是 `WOT_STARTUP_MUTEX`**。

## 4. WGC 导出（C 接口子集）

`wgc_api.dll` 直接导出（非 C++ 修饰）：

- `WGCApiCreateInstance` @ `0x0002C810`
- `WGCApiCreateInstanceEx` @ `0x0002C830`
- `WGCApiGetResultDescription` @ `0x0002C9A0`
- `WGCApiMain` / `WGCApiMainA` @ `0x0002CCC0`
- `WGCApiMainW` @ `0x0002CC10`

另有大量 `binding_WGCApi*` 薄封装（cereal IPC 绑定），包括：

- `binding_WGCApiIsAnotherGameRunning`
- `binding_WGCApiHighlightAnotherInstance`
- `binding_WGCApiCreateGlobalInstance` / `FreeGlobalInstance`

## 5. 采用的解除策略（M0）

因 **未** 得到 0.9.22 式 cleanup thunk 的 x64 RVA，M0 采用保守策略：

1. **PE 精确校验**：Machine / TimeDateStamp / ImageBase / SizeOfImage 全匹配才允许操作。
2. **句柄枚举**：`NtQuerySystemInformation(SystemExtendedHandleInformation)` + `NtQueryObject(ObjectNameInformation)`，仅处理**当前进程**句柄。
3. **名称白名单**（大小写不敏感子串）：
   - `WOT_STARTUP_MUTEX`
   - `wot_client_mutex`
   - `wgc_running_games_mtx` / `wgcs_*` / `wgc360_*`
   - `wgc_game_mtx_`
   - `AppMutex`
4. 对匹配句柄：`ReleaseMutex` + `CloseHandle`。
5. 复核：`OpenMutex` 探针确认目标名不再可见。

### 待验证项

| 编号 | 项 | 验证方法 |
|---|---|---|
| V1 | `WOT_STARTUP_MUTEX` 是否带 `Global\`/`Local\` 前缀 | 启动客户端后用 Process Explorer / 自写枚举列出对象名 |
| V2 | 引擎在启动检查后是否继续依赖该互斥体 | 多开后跑战斗/退出，观察是否崩溃 |
| V3 | x64 WGC cleanup thunk RVA | IDA/Ghidra 交叉引用 `WGCControllerImpl` 析构与 `AppMutexWin32` |
| V4 | `wgc_game_mtx_` 后缀格式（gameFolder hash?） | 运行时对象名 dump |
| V5 | 关闭引擎持有的互斥句柄是否与 0.9.22 一样安全 | 长时间多开压力测试 |

## 6. Python 桥接决策

- 产物：`vvg_instance_guard_native.pyd`（实际为 x64 DLL，含 `initvvg_instance_guard_native` 与 C 导出）。
- Python 侧优先 `ctypes.CDLL` 调用 C 导出（`vvg_release_client_guard` 等），避免依赖 `imp.load_dynamic` 对纯 DLL 的 init 行为。
- 同时保留 `initvvg_instance_guard_native` / `initinstance_guard_native` 供将来 `imp.load_dynamic`。
- `install_atmosphere_owner_guard` 在 2.3.1.2 **未映射**，返回状态 `22`；Python 接口不要求其成功（0.9.22 专属修复）。

## 7. 环境变量约定

| 变量 | 含义 |
|---|---|
| `VVG_ALLOW_MULTIPLE_CLIENTS=1` | 启用 `release_if_requested` |
| `VVG_CLIENT_MODE` | `simulation_worker` / `player` |
| `VVG_HIDDEN_DESKTOP` | worker 私有桌面提示 |
| `VVG_WORKER_READY_MARKER` | worker 就绪文件路径 |
| `VVG_INSTANCE_GUARD_PATH` | 显式指定 native bridge 路径（测试/启动器） |

## 8. 分析工具

- `tools/scan_multiclient_strings.py` — PE 字符串扫描
- `tools/analyze_wgc_2312.py` — 导出/导入/WGC API
- `tools/analyze_mutex_names.py` — 互斥体命名上下文

## 9. 风险与后续

1. **句柄关闭**与 0.9.22 的“调用引擎 cleanup”不同：若引擎稍后 `WaitForSingleObject` 同一对象，可能得到伪句柄语义差异。M0 之后应用双开实测。
2. 若 `WOT_STARTUP_MUTEX` 只在启动瞬间使用，关闭后风险低；若被长持有，需改回“引擎内部 cleanup”路径（V3）。
3. WGC 变体 DLL（EU/NA/360）名称不同，白名单已覆盖三种前缀。
4. 离线环境 WGC 软失败意味着 AppMutex 路径可能是死代码；仍保留以兼容带 WGC 的机器。

## 10. 结论

- 已确认 2.3.1.2 的 PE 身份与主要单实例互斥体命名。
- 已确认可用 `python27.dll` 动态符号替代 RVA 桥接。
- 已交付可编译的 x64 native guard + starter + Python 接口 + 单元测试。
- cleanup thunk 与精确对象名运行时形态标记为**待验证**，并给出验证步骤。
