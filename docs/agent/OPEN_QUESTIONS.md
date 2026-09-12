# OPEN_QUESTIONS.md

> 开放问题 — 需要用户确认或后续验证的问题

## 问题：多实例方案选择

- **为什么需要确认**：多实例解除有多种方案，各有优缺点，影响后续开发方向
- **可选方案**：
  1. **native C x64 + 引擎 WGC cleanup thunk**（推荐）
     - 优点：参考项目已验证类似方案
     - 缺点：需要逆向 2.3.1.2 的 WGC 结构
  2. **DLL 注入 Hook CreateMutexW/OpenMutexW**
     - 优点：不依赖 WGC 结构
     - 缺点：需要 DLL 注入，更复杂
  3. **独立用户会话 / 沙箱**
     - 优点：不需要修改游戏
     - 缺点：部署复杂，用户体验差
  4. **虚拟机**
     - 优点：完全隔离
     - 缺点：性能差，部署复杂
- **当前假设**：方案 1（native C x64 + 引擎 WGC cleanup thunk）
- **是否阻塞**：**是**（进入编码阶段前必须解决）
- **证据**：
  - 参考项目 `offline_instance_guard_native.c` 已验证类似方案
  - `instance_guard.py` 使用 `OFFLINE_LAN_0922_ALLOW_MULTIPLE_CLIENTS` 环境变量
  - 互斥体名 `wot_client_mutex`
  - 0.9.22 是 32-bit，2.3.1.2 是 64-bit，必须重写

## 问题：客户端部署方式

- **为什么需要确认**：部署方式影响 mod 加载和更新
- **可选方案**：
  1. **res_mods 散装脚本**（推荐）
     - 优点：简单，易于调试
     - 缺点：文件较多
  2. **wotmod 打包**
     - 优点：文件少，易于分发
     - 缺点：调试不便
- **当前假设**：方案 1（res_mods 散装脚本）
- **是否阻塞**：否
- **证据**：
  - Offline2.3.1.2 使用 `res_mods/2.3.1.2/scripts/client/gui/mods/`
  - 用户明确要求"游戏启动方式是直接打开游戏 exe，游戏自动加载 res_mods 里面的 .pyc"

## 问题：Bot AI 范围

- **为什么需要确认**：Bot AI 复杂度影响工作量
- **可选方案**：
  1. **基础 Bot**（推荐）
     - 简单的移动、射击、目标选择
     - 从 Offline2.3.1.2 的 bots.py 简化
  2. **完整 Bot**
     - 完整的 AI 行为（导航、战术、弹药选择）
     - 从参考项目移植
- **当前假设**：方案 1（基础 Bot），后续迭代完善
- **是否阻塞**：否
- **证据**：
  - Offline2.3.1.2 有 `bots.py` (95 KB) 和 `bot_routes.py` (3 KB)
  - 参考项目有完整的 Bot AI 系统

## 问题：单人模式处理

- **为什么需要确认**：用户要求"不保留单机模式"，但单人也需要能玩
- **可选方案**：
  1. **单人也启动 sim-worker**（推荐）
     - 优点：架构统一
     - 缺点：需要启动额外进程
  2. **单人使用内置 sim-worker**
     - 优点：用户体验好
     - 缺点：架构复杂
- **当前假设**：方案 1（单人也启动 sim-worker）
- **是否阻塞**：否
- **证据**：
  - 用户明确要求"单人运行时也连接本地 sim-worker"
  - 参考项目 README: "Single player: you play alone against bots. The launcher runs the server for you; every battle uses the same LAN authority path."

## 问题：2.3.1.2 互斥体名

- **为什么需要验证**：不知道 2.3.1.2 的互斥体名
- **验证方法**：
  1. 使用 Process Explorer 观察运行时互斥体
  2. 使用 Process Monitor 捕获 CreateMutexW 调用
  3. 反编译 wgc_api.dll
- **当前假设**：可能是 `wot_client_mutex`（与 0.9.22 相同）
- **是否阻塞**：**是**（M0 任务）
- **证据**：
  - 0.9.22 使用 `wot_client_mutex`
  - 2.3.1.2 有三个 WGC DLL，结构可能不同

## 问题：2.3.1.2 WGC cleanup thunk RVA

- **为什么需要验证**：不知道 2.3.1.2 的 WGC cleanup thunk RVA
- **验证方法**：
  1. 反编译 WorldOfTanks.exe
  2. 分析 WGC 初始化代码
  3. 参考 0.9.22 的 RVA
- **当前假设**：需要逆向分析
- **是否阻塞**：**是**（M0 任务）
- **证据**：
  - 0.9.22 使用 `RVA_WGC_CLEANUP_THUNK 0x004b7180U`
  - 2.3.1.2 是 x64，RVA 完全不同

## 问题：2.3.1.2 Python .pyc magic number

- **为什么需要验证**：不知道 2.3.1.2 的 .pyc magic number
- **验证方法**：
  1. 检查游戏目录中的 .pyc 文件
  2. 使用 win64/python27.dll 编译测试
- **当前假设**：与 0.9.22 相同（`03 f3 0d 0a`）
- **是否阻塞**：否（M5 任务）
- **证据**：
  - Offline2.3.1.2 所有代码是 Python 2.7
  - bytecode magic `62211` (0x7203) — 注意：这可能是 uncompyle6 的显示方式，实际 magic 可能不同

## 问题：openwg mod 功能

- **为什么需要验证**：不知道 openwg mod 的功能，可能冲突
- **验证方法**：
  1. 分析 openwg_*.pyd 的导出函数
  2. 测试共存
- **当前假设**：可能是网络/音频/字体相关的 mod
- **是否阻塞**：否
- **证据**：
  - `mods/temp/net.openwg.audio/native_wg/openwg_audio.pyd`
  - `mods/temp/net.openwg.filewatcher/native_wg/openwg_filewatcher.pyd`
  - `mods/temp/net.openwg.fonts/native_wg/openwg_fonts.pyd`
  - `mods/temp/net.openwg.native/native_wg/openwg_native.pyd`
  - `mods/temp/net.openwg.native.hooks/native/openwg_native_hooks.dll`
  - `mods/temp/net.openwg.network/native_wg/openwg_network.pyd`

## 问题：BigWorld API 具体变化

- **为什么需要验证**：不知道 2.3.1.2 的 BigWorld API 具体变化
- **验证方法**：
  1. 从 Offline2.3.1.2 提取 API 用法
  2. 对比 0.9.22 的 API
  3. 逐步验证
- **当前假设**：有变化，特别是载具机制系统
- **是否阻塞**：否（M4 任务）
- **证据**：
  - Offline2.3.1.2 有 `mechanics.py` (243 KB) 的机制系统
  - 2.3.1.2 引入了 `vehicles.mechanics.*` 模块

## 问题：战斗模式范围

- **为什么需要确认**：需要支持哪些战斗模式
- **可选方案**：
  1. **标准战斗**（15v15）（推荐）
  2. **车库战**（任意车辆）
  3. **自定义房间**
- **当前假设**：方案 1（标准战斗），后续扩展
- **是否阻塞**：否
- **证据**：
  - Offline2.3.1.2 支持标准战斗
  - 参考项目支持标准战斗
  - 用户要求"两个客户端能进入同一场战斗"

## 问题：地图支持范围

- **为什么需要确认**：需要支持哪些地图
- **可选方案**：
  1. **少量核心地图**（推荐）
  2. **全部地图**
- **当前假设**：方案 1（少量核心地图），后续扩展
- **是否阻塞**：否
- **证据**：
  - 参考项目支持 41 张地图
  - 需要烘焙导航图数据
  - 优先验证核心功能
