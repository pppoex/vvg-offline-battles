# HANDOFF.md

> 交接记录 — 给下一个 Agent 的最重要文件

## 当前阶段

**M0 编码启动：多实例限制解除（2.3.1.2 x64）已落地**

第一阶段分析已完成；本轮按用户任务进入 M0 实现。

## 最后 commit

- **hash**: 待提交（本轮 M0 产物）
- **message**: 建议 `feat(multiclient): 实现 2.3.1.2 x64 多实例守卫 [TASK-M0]`
- **文件**: src/multiclient/**, docs/analysis/multiclient-research.md, tests/unit/test_instance_guard.py, tools/*.py

## 已完成

1. **TASK-000**: 初始化工作区与 AGENTS.md
2. **TASK-001**: Offline2.3.1.2 只读扫描与分析
3. **TASK-002**: wot-offline-battles 参考项目扫描
4. **TASK-003**: 版本差异分析
5. **TASK-004**: 目标架构设计与迁移计划
6. **TASK-005**: 多实例限制专项分析
7. **TASK-006**: 任务拆解与风险文档
8. **TASK-M0**: 多实例 native 实现
   - PE 逆向：Machine/TimeDateStamp/ImageBase/SizeOfImage 已测量
   - 主互斥体：`WOT_STARTUP_MUTEX`（非 `EWOT_*`）
   - Python：`python27.dll` 全量导出 `Py_InitModule4_64` / `PyInt_FromLong`
   - 交付 native guard + worker starter + Python 接口 + 单测
   - 编译成功；`unittest` 13/13 通过

## 未完成

1. **真机双开联机验证**（需用户在游戏内确认互斥体名与稳定性）
2. **WGC cleanup thunk x64 RVA 逆向**（报告 V3；当前用句柄枚举替代）
3. **install_atmosphere_owner_guard**（0.9.22 专属，2.3.1.2 返回 22，未实现 tick 补丁）
4. **sim-worker 联机协议移植**（后续里程碑）

## 正在处理

- M0 交付物已齐；等待真机验证与用户确认进入 M1

## 下一步建议

1. 用 `dist/multiclient/vvg_worker_starter.exe` 双开验证
2. 在游戏进程内调用 `instance_guard.release_if_requested()` 验证 `WOT_STARTUP_MUTEX` 是否消失
3. Process Explorer 确认真实对象名（报告 V1/V4）
4. 若句柄关闭导致崩溃，转入 IDA 定位 cleanup thunk（V3）

## 关键文件

### 本轮新增

- `src/multiclient/native/instance_guard.c`
- `src/multiclient/native/worker_starter.c`
- `src/multiclient/native/build.ps1`
- `src/multiclient/instance_guard.py`
- `docs/analysis/multiclient-research.md`
- `tests/unit/test_instance_guard.py`
- `tools/scan_multiclient_strings.py`
- `tools/analyze_wgc_2312.py`
- `tools/analyze_mutex_names.py`

### 产物（不入库，见 .gitignore）

- `dist/multiclient/vvg_instance_guard_native.pyd`
- `dist/multiclient/vvg_worker_starter.exe`

### 分析文档

- `docs/analysis/multiclient-research.md` — M0 逆向报告
- `docs/analysis/01-offline2312-project-scan.md` — Offline 扫描

### 流程文档

- `AGENTS.md`
- `docs/agent/PROGRESS.md`
- `docs/agent/HANDOFF.md`

### 源项目（只读）

- `D:\Projects\Offline2.3.1.2`
- `D:\Projects\wot-offline-battles`
- `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2`

## 关键发现

### 2.3.1.2 PE

- exe: `0x8664` / `0x6A759054` / base `0x140000000` / size `0x0509F000`
- 独立 `python27.dll` 导出完整 CPython API（与 0.9.22 exe 内嵌 RVA 不同）

### 多实例

- 主闸门：`WOT_STARTUP_MUTEX`（app.cpp）
- WGC：`wgc_game_mtx_` / `wgc_running_games_mtx`；离线 WGC 软失败
- 无 `wot_client_mutex` 完整字符串（仅孤立 `wot_client`）

## 风险

1. 句柄枚举关闭与 0.9.22 引擎 cleanup 不同 — 需真机验证
2. atmosphere 补丁未映射 — 若 2.3.1.2 仍有 hangar 环境问题需另做
3. WGC 变体 DLL 命名差异 — 白名单已覆盖 EU/NA/360

## 待用户确认

1. M0 真机双开是否通过
2. 是否继续 M1（sim-worker 协议）

## 禁止事项提醒

- 禁止修改 `D:\Projects\Offline2.3.1.2`
- 禁止修改 `D:\Projects\wot-offline-battles`
- 禁止修改游戏安装目录、exe、dll、核心资源
- 禁止无证据编造 API、文件、协议
- 禁止把大量代码写进单文件
- 禁止跳过测试和文档
