# DECISIONS.md

> 决策记录 — ADR 风格

## 决策：项目架构采用权威服务器 + 薄客户端模型

- **背景**：需要将单机 mod 改造为联机架构，支持多玩家
- **选项**：
  1. 客户端权威（P2P）
  2. 服务器权威 + 薄客户端
  3. 混合模型
- **结论**：采用服务器权威 + 薄客户端模型
- **影响**：
  - 所有游戏状态由 sim-worker 决定
  - 客户端只负责输入、渲染、UI、预测
  - 单人也必须连接本地 sim-worker
- **证据**：
  - 参考项目 `wot-offline-battles` 已验证此模型
  - `CLAUDE.md:182-191`: "Every room has one mandatory hidden native worker"
  - 用户明确要求服务器权威

## 决策：协议采用 JSON lines over TCP

- **背景**：需要定义客户端-服务器-Worker 之间的通信协议
- **选项**：
  1. JSON lines over TCP
  2. MessagePack over TCP
  3. 二进制自定义协议
  4. gRPC
- **结论**：采用 JSON lines over TCP
- **影响**：
  - 可读性好，调试方便
  - Python 标准库支持
  - 性能足够（LAN 环境）
- **证据**：
  - 参考项目 `lan_client.py:31` 使用 JSON lines
  - 参考项目 `lan_battle_server.py` 使用 JSON lines
  - PROTOCOL_VERSION = 5

## 决策：服务器使用 Python 3

- **背景**：需要选择服务器实现语言
- **选项**：
  1. Python 3
  2. Python 2.7
  3. C++
  4. Go
- **结论**：使用 Python 3
- **影响**：
  - 不受客户端 Python 2.7 限制
  - 可用现代 Python 特性
  - asyncio 支持好
- **证据**：
  - 参考项目 `server/lan_battle_server.py` 使用 Python 3
  - `from __future__ import annotations` 语法
  - 参考项目使用 dataclasses, typing

## 决策：客户端使用 Python 2.7

- **背景**：客户端必须与游戏内嵌 Python 兼容
- **选项**：
  1. Python 2.7（必须）
- **结论**：使用 Python 2.7
- **影响**：
  - 只能用标准库
  - 无法使用现代 Python 特性
  - 需要注意 Python 2/3 兼容性
- **证据**：
  - `python.log`: "WorldOfTanks(x64) 2.3.1.10157"
  - `win64/python27.dll` 存在
  - Offline2.3.1.2 所有代码是 Python 2.7

## 决策：多实例方案采用 native C x64 + 引擎 WGC cleanup thunk

- **背景**：需要解除游戏单实例限制，允许多客户端同时运行
- **选项**：
  1. native C x64 + 引擎 WGC cleanup thunk（推荐）
  2. DLL 注入 Hook CreateMutexW/OpenMutexW
  3. 独立用户会话 / 沙箱
  4. 虚拟机
- **结论**：采用方案 1（native C x64 + 引擎 WGC cleanup thunk）
- **影响**：
  - 需要逆向 2.3.1.2 的 WGC 结构
  - 需要编写 x64 native C 代码
  - 参考 0.9.22 的实现思路
- **证据**：
  - 参考项目 `offline_instance_guard_native.c` 已验证类似方案
  - `instance_guard.py` 使用 `OFFLINE_LAN_0922_ALLOW_MULTIPLE_CLIENTS` 环境变量
  - 互斥体名 `wot_client_mutex`
  - 0.9.22 是 32-bit，2.3.1.2 是 64-bit，必须重写
- **状态**：**待用户确认**

## 决策：客户端部署采用 res_mods 散装脚本

- **背景**：需要选择客户端 mod 部署方式
- **选项**：
  1. res_mods 散装脚本（推荐）
  2. wotmod 打包
- **结论**：采用方案 1（res_mods 散装脚本）
- **影响**：
  - 简单，易于调试
  - 文件较多
- **证据**：
  - Offline2.3.1.2 使用 `res_mods/2.3.1.2/scripts/client/gui/mods/`
  - 用户明确要求"游戏启动方式是直接打开游戏 exe，游戏自动加载 res_mods 里面的 .pyc"
- **状态**：**待用户确认**

## 决策：单人模式也启动 sim-worker

- **背景**：用户要求"不保留单机模式"，但单人也需要能玩
- **选项**：
  1. 单人也启动 sim-worker（推荐）
  2. 单人使用内置 sim-worker
- **结论**：采用方案 1（单人也启动 sim-worker）
- **影响**：
  - 架构统一
  - 需要启动额外进程
- **证据**：
  - 用户明确要求"单人运行时也连接本地 sim-worker"
  - 参考项目 README: "Single player: you play alone against bots. The launcher runs the server for you; every battle uses the same LAN authority path."
- **状态**：**待用户确认**

## 决策：Bot AI 采用基础版本

- **背景**：需要决定 Bot AI 的复杂度
- **选项**：
  1. 基础 Bot（推荐）
  2. 完整 Bot
- **结论**：采用方案 1（基础 Bot），后续迭代完善
- **影响**：
  - 简单的移动、射击、目标选择
  - 从 Offline2.3.1.2 的 bots.py 简化
- **证据**：
  - Offline2.3.1.2 有 `bots.py` (95 KB) 和 `bot_routes.py` (3 KB)
  - 参考项目有完整的 Bot AI 系统
  - 优先实现核心功能
- **状态**：**待用户确认**

## 决策：第一阶段只做只读分析

- **背景**：用户明确要求第一阶段只做只读侦察、分析和方案设计
- **选项**：
  1. 只读分析（必须）
  2. 边分析边编码
- **结论**：严格只读分析
- **影响**：
  - 不写业务代码
  - 不修改游戏客户端
  - 不修改参考项目
  - 不修改单机 mod 源项目
- **证据**：
  - 用户明确要求"第一阶段只做只读侦察、分析和方案设计，不要写业务代码"
  - 用户明确要求"在第一阶段完成并等我确认前，不要创建或修改任何业务代码"
- **状态**：已执行

## 决策：多实例守卫通过 res_mods 游戏 mod 在进程内释放

- **背景**：M0 只交付了 native pyd + Python 接口，游戏内无人调用
  `release_if_requested()`，双开仍弹 "already running"
- **选项**：
  1. 仅依赖 starter 环境变量（无效——不会被游戏执行）
  2. DLL 注入到更早的 C++ 阶段
  3. 仿 0.9.22：res_mods mod 在 Python init 时释放本进程互斥句柄
- **结论**：选项 3
- **影响**：
  - 第一个客户端必须先过 mod init 再开第二个
  - 与 0.9.22 行为对齐；mod 名独立为 `vvg_instance_guard`
  - starter 对 player/worker 均设置 `VVG_ALLOW_MULTIPLE_CLIENTS=1`
- **证据**：
  - 参考 `offline_lan_0922/bootstrap.py` init() 调用 release_if_requested
  - 用户复现：`vvg_worker_starter.exe --player` 第二实例弹对话框
- **状态**：已验证通过

## 决策：游戏 mod 必须编译为 .pyc

- **背景**：部署 .py 到 res_mods 后游戏不加载 mod
- **选项**：
  1. 编译为 .pyc（必须）
  2. 同时部署 .py 和 .pyc
- **结论**：同时部署 .py（保留源码）和 .pyc（游戏实际加载）
- **影响**：
  - 部署脚本必须用 Python 2.7 的 `py_compile`
  - 必须校验 magic number = 62211 (`03 f3 0d 0a`)
  - 不可用 Python 3 编译（magic 不兼容）
- **证据**：
  - 用户反馈：游戏不直接读取 .py
  - Offline2.3.1.2 反编译头：`Python bytecode version base 2.7 (62211)`
- **状态**：已验证通过

## 决策：游戏内 native pyd 用 imp.load_dynamic 导入

- **背景**：`ctypes.CDLL` 在游戏内嵌 Python 中失败，报 `No module named _ctypes`
- **选项**：
  1. `imp.load_dynamic` 作为 C 扩展导入（推荐）
  2. 修复 ctypes 依赖（不可行——游戏不提供 _ctypes）
  3. 完全不用 Python，改为 DLL 注入
- **结论**：选项 1
- **影响**：
  - native pyd 必须导出 `initvvg_instance_guard_native` 函数
  - Python 侧优先 `imp.load_dynamic`，ctypes 仅作宿主回退
  - 单元测试需区分系统 Python 与游戏内嵌环境差异
- **证据**：
  - 游戏日志：`release failed: No module named _ctypes`
  - 参考项目 `instance_guard.py` 也使用 `imp.load_dynamic`
- **状态**：已验证通过

## 决策：主互斥体是 WOT_STARTUP_MUTEX

- **背景**：需要确定 2.3.1.2 的单实例互斥体名
- **选项**：
  1. 假设与 0.9.22 相同（`wot_client_mutex`）— 错误
  2. 逆向分析确定实际名称
- **结论**：选项 2，确认主闸门是 `WOT_STARTUP_MUTEX`
- **影响**：
  - native 守卫的白名单必须包含 `WOT_STARTUP_MUTEX`
  - WGC AppMutex（`wgc_game_mtx_` 等）作为补充
- **证据**：
  - PE 字符串扫描：UTF-16 `WOT_STARTUP_MUTEX` 紧邻 `app.cpp`
  - 参考项目是 `wot_client_mutex`（0.9.22 专属）
- **状态**：已验证通过

## 决策：进入编码阶段

- **背景**：第一阶段分析完成，用户确认 M0 方向后进入编码
- **结论**：M0（多实例）优先，已完成并验证
- **影响**：
  - 后续按 M1-M9 里程碑推进
  - 每个里程碑完成后运行测试、更新文档、提交 commit
- **状态**：已进入

## 决策：SDK 模块保持 Python 2/3 双兼容

- **背景**：客户端运行 Python 2.7，服务器/测试运行 Python 3；SDK 会被两端共用
- **选项**：
  1. SDK 双兼容（2/3）
  2. SDK 只写 Py2，服务器另写一份
  3. SDK 只写 Py3，客户端 mod 不用 SDK
- **结论**：选项 1
- **影响**：
  - 禁止 f-string、运行时类型注解、dataclass、pathlib
  - 使用 `from __future__ import absolute_import, division, print_function`
  - `class Foo(object)` 风格；`__div__` + `__truediv__` 双定义
- **证据**：
  - `DECISIONS`：客户端 Python 2.7、服务器 Python 3
  - Offline2.3.1.2 与参考项目均为游戏内 Py2.7
- **状态**：已执行（M1）

## 决策：config 不复制 Offline 单机假服务器配置

- **背景**：Offline `config.py` 约 882 行，绝大多数是单机战斗/Bot/结果参数
- **选项**：
  1. 整文件复制后删改
  2. 只保留 JSON override 机制 + 联机网络默认值（重写精简版）
- **结论**：选项 2
- **影响**：
  - 移除 `OFFLINE_URL` / `OFFLINE_NAME` / 大量 BATTLE_* 单机开关
  - 新增 `SERVER_HOST/PORT`、`CLIENT_MODE`、重连策略、tick 率
  - 后续 sim-worker 需要的战斗参数在 M3 按需迁入，不进 SDK config
- **证据**：
  - `05-migration-and-sdk-plan.md` §2.2 要求移除单机特定配置
  - 用户使命：不保留单机模式
- **状态**：已执行（M1）

## 决策：数学库自实现而非引入 numpy（客户端路径）

- **背景**：sim-worker 与客户端预测都需要 Vector3/Matrix
- **选项**：
  1. 纯 Python 自实现对齐 BigWorld API
  2. 服务器用 numpy，客户端另写
- **结论**：先选项 1（M1）；若 M3 服务器性能不足再对 sim-worker 内部换 numpy，对外接口不变
- **影响**：
  - 客户端 2.7 无第三方依赖
  - 接口：`translation`、`yaw/pitch/roll`、`applyPoint`/`applyVector`
- **证据**：
  - 客户端只能用标准库
  - Offline 大量使用 `Math.Vector3` / `Math.Matrix`
- **状态**：已执行（M1）
