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
