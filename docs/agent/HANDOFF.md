# HANDOFF.md

> 交接记录 — 给下一个 Agent 的最重要文件

## 当前阶段

**M0.1：多实例守卫已接入游戏 mod 并部署**

M0 native 实现已落地；本轮补齐 **游戏内调用点**（BigWorld mod）与部署脚本，
修复 `--player` 清除多开环境变量的 bug。

## 最后 commit

- **hash**: `3e9e969`（本轮后更新）
- **message**: `feat(multiclient): 接入游戏 mod 释放实例守卫 [TASK-M0.1]`
- **文件**: src/client/**, src/deploy/install_multiclient.py, src/multiclient/**, tests/unit/, docs/**

## 已完成

1. **TASK-000**: 初始化工作区与 AGENTS.md
2. **TASK-001**: Offline2.3.1.2 只读扫描与分析
3. **TASK-002**: wot-offline-battles 参考项目扫描
4. **TASK-003**: 版本差异分析
5. **TASK-004**: 目标架构设计与迁移计划
6. **TASK-005**: 多实例限制专项分析
7. **TASK-006**: 任务拆解与风险文档
8. **TASK-M0**: 多实例 native 实现
9. **TASK-M0.1**: 游戏 mod 集成
   - `src/client/mod_vvg_instance_guard.py` — BigWorld 入口
   - `src/client/vvg_instance_guard/bootstrap.py` — 调用 `release_if_requested`
   - `src/deploy/install_multiclient.py` — 部署到 res_mods / mods / win64
   - starter：player + worker 均设 `VVG_ALLOW_MULTIPLE_CLIENTS=1` 与
     `VVG_INSTANCE_GUARD_PATH`
   - path 解析支持 2.3.1.2 的 `win64/` + 根级 `mods/` 布局
   - `unittest` 22/22 通过；已写入游戏目录附属文件
10. **TASK-M0.2**: res_mods 只加载 .pyc — 部署脚本增加 Python 2.7 编译
   - **发现**：2.3.1.2 客户端只加载 `.pyc`，不读 `.py` 源文件
   - `install_multiclient.py` 用 `D:\Python27\python.exe`（或 `.py27` 符号链接）
     的 `py_compile` 生成 `.pyc`，并校验 magic `62211` / 字节 `03 f3 0d 0a`
   - 同时保留 `.py` 与 `.pyc` 部署到 res_mods
   - **magic 更正**：任务描述中的 `03 72 0d 0a` 有误（0x7203≠62211）；
     实际 Python 2.7 magic = 62211 = 0xF303 → 字节 `03 f3 0d 0a`
   - 新增单测 `test_compile_pyc_magic_is_py27`；Py2.7 下 23/23 通过
   - 游戏目录已部署 4 个 `.pyc`（magic 均已独立验证）

## 未完成

1. **真机双开联机验证**（用户确认；需先开满第一个客户端再开第二个）
2. **WGC cleanup thunk x64 RVA 逆向**（报告 V3；当前用句柄枚举替代）
3. **install_atmosphere_owner_guard**（0.9.22 专属，2.3.1.2 返回 22）
4. **sim-worker 联机协议移植**（后续里程碑）

## 正在处理

- M0.1 + M0.2 交付完成；等待用户真机双开确认（mod 以 .pyc 加载）

## 下一步建议

1. 用 `win64\vvg_worker_starter.exe --player` 开满第一个客户端到登录界面
2. 再用第二个 `vvg_worker_starter.exe --player` 开第二个，确认无 “already running”
3. 若仍有对话框：用 Process Explorer 查 `WOT_STARTUP_MUTEX` 是否带额外前缀（V1）
4. 查游戏 python 日志是否出现 `[VVG instance guard] released ...`

## 关键文件

### M0

- `src/multiclient/native/instance_guard.c`
- `src/multiclient/native/worker_starter.c`
- `src/multiclient/native/build.ps1`
- `src/multiclient/instance_guard.py`
- `docs/analysis/multiclient-research.md`
- `tests/unit/test_instance_guard.py`

### M0.1 / M0.2（本轮）

- `src/client/mod_vvg_instance_guard.py`
- `src/client/vvg_instance_guard/__init__.py`
- `src/client/vvg_instance_guard/bootstrap.py`
- `src/deploy/install_multiclient.py` — 含 py_compile + magic 校验
- `tests/unit/test_bootstrap_and_deploy.py`

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
- **M0.1**：释放入口在 `mod_vvg_instance_guard.init()` →
  `bootstrap.init()` → `instance_guard.release_if_requested()`
- starter 必须设 `VVG_ALLOW_MULTIPLE_CLIENTS=1` **和**
  `VVG_INSTANCE_GUARD_PATH`（player 与 worker 都要）
- **M0.2**：客户端只加载 res_mods 中的 `.pyc`；
  Python 2.7 bytecode magic = 62211 (`03 f3 0d 0a`)；
  部署必须用 Py2.7 编译，不可用 Py3 的 py_compile

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
