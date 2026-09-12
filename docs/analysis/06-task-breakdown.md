# 06 - 任务拆解

> 拆解时间：2026-09-12
> 说明：分里程碑、分阶段的任务拆解，每个任务包含目标、输入、输出、依赖、验收标准、测试方式

## 里程碑总览

```
M0: 多实例限制解除方案（最高优先级）
M1: 项目骨架与 SDK 抽取
M2: 协议与序列化
M3: sim-worker 权威服务器循环
M4: 薄客户端补丁
M5: 命令行启动器与部署
M6: 基础同步（进入战斗、移动、炮塔）
M7: 战斗同步（开火、命中、伤害、死亡）
M8: 断线重连
M9: 测试、文档、稳定性收尾
```

---

## M0: 多实例限制解除方案

### 目标

让同一台机器可以运行多个游戏客户端实例，用于联机和本地测试。

### 交付物

1. `docs/analysis/multiclient-research.md` — 调研文档
2. 推荐方案及可行性分析
3. 原型验证（编码阶段）

### 任务列表

#### M0.1: 逆向 2.3.1.2 单实例机制

- **目标**：确定 2.3.1.2 的单实例限制机制
- **输入**：
  - `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\win64\WorldOfTanks.exe`
  - `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\win64\wgc_api.dll`
  - `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\python.log`
- **输出**：
  - 互斥体名列表
  - WGC 结构布局
  - 关键 RVA 偏移
- **依赖**：无
- **验收标准**：
  - 找到至少一个命名互斥体
  - 确认 WGC cleanup thunk 的 RVA
  - 确认 WGC holder 的 RVA
- **测试方式**：
  - 使用 Process Explorer / Process Monitor 观察运行时行为
  - 使用 PE 分析工具提取 RVA

#### M0.2: 设计解除方案

- **目标**：设计 2.3.1.2 的多实例解除方案
- **输入**：M0.1 的逆向结果
- **输出**：`docs/analysis/multiclient-research.md`
- **依赖**：M0.1
- **验收标准**：
  - 文档包含推荐方案
  - 文档包含可行性分析
  - 文档包含风险评估
- **测试方式**：文档评审

#### M0.3: 实现 x64 native 实例守卫

- **目标**：实现 2.3.1.2 的 x64 实例守卫
- **输入**：M0.2 的设计文档
- **输出**：
  - `src/multiclient/native/instance_guard.c`
  - `src/multiclient/native/instance_guard.pyd`（编译产物）
- **依赖**：M0.2
- **验收标准**：
  - 编译成功（x64）
  - 能释放 WGC 互斥体
  - 能隐藏/显示窗口
- **测试方式**：
  - `tests/unit/test_instance_guard.py`
  - 手动启动两个客户端验证

#### M0.4: 实现 worker 启动器

- **目标**：实现 2.3.1.2 的 worker 启动器
- **输入**：M0.3 的 native 守卫
- **输出**：
  - `src/multiclient/native/worker_starter.c`
  - `src/multiclient/native/worker_starter.exe`（编译产物）
- **依赖**：M0.3
- **验收标准**：
  - 能无窗口启动客户端
  - 能隐藏主窗口
  - worker ready 信号正常
- **测试方式**：
  - `tests/unit/test_worker_starter.py`
  - 手动启动 worker 验证

### 验收标准（里程碑）

- 两个客户端可同时启动并进入登录/战斗
- 进程、窗口、互斥体检查通过

### 测试方式

- 启动两个 exe，检查进程、窗口、互斥体

### 风险

- 反调试、完整性校验、C 扩展保护
- Python 层无法解决
- 需要专门的逆向分析

---

## M1: 项目骨架与 SDK 抽取

### 目标

建立项目骨架，从 Offline2.3.1.2 抽取可复用 SDK。

### 交付物

1. 项目目录结构
2. `src/sdk/` 基础模块
3. `pyproject.toml`
4. 单元测试框架

### 任务列表

#### M1.1: 创建项目骨架

- **目标**：创建项目目录结构和配置文件
- **输入**：`docs/analysis/04-target-architecture.md`
- **输出**：
  - `pyproject.toml`
  - `src/` 目录结构
  - `tests/` 目录结构
  - `docs/` 目录结构
- **依赖**：无
- **验收标准**：
  - 目录结构符合设计
  - `pyproject.toml` 配置正确
  - pytest 可运行
- **测试方式**：`pytest --collect-only`

#### M1.2: 抽取 SDK 基础模块

- **目标**：从 Offline2.3.1.2 抽取 SDK 基础模块
- **输入**：
  - `Offline2.3.1.2/hooks.py`
  - `Offline2.3.1.2/log.py`
  - `Offline2.3.1.2/config.py`
- **输出**：
  - `src/sdk/hooks.py`
  - `src/sdk/log.py`
  - `src/sdk/config.py`
- **依赖**：M1.1
- **验收标准**：
  - 模块可导入
  - 单元测试通过
  - 无 BigWorld 依赖
- **测试方式**：
  - `tests/unit/test_hooks.py`
  - `tests/unit/test_log.py`
  - `tests/unit/test_config.py`

#### M1.3: 实现数学库

- **目标**：实现向量/矩阵数学库
- **输入**：无
- **输出**：
  - `src/sdk/math/__init__.py`
  - `src/sdk/math/vector.py`
  - `src/sdk/math/matrix.py`
- **依赖**：M1.1
- **验收标准**：
  - 向量运算正确
  - 矩阵运算正确
  - 单元测试通过
- **测试方式**：`tests/unit/test_math.py`

#### M1.4: 实现基础接口

- **目标**：实现实体/组件/事件基础接口
- **输入**：无
- **输出**：
  - `src/sdk/entity/base.py`
  - `src/sdk/component/base.py`
  - `src/sdk/event/bus.py`
  - `src/sdk/interface/protocols.py`
- **依赖**：M1.1
- **验收标准**：
  - 接口定义清晰
  - 单元测试通过
- **测试方式**：`tests/unit/test_sdk_interfaces.py`

### 验收标准（里程碑）

- 项目骨架建立完成
- SDK 基础模块可用
- 单元测试框架运行

### 测试方式

- `pytest tests/unit/`

### 风险

- Offline2.3.1.2 代码质量（Decompile++ artifact）
- Python 2.7 → 3 兼容性

---

## M2: 协议与序列化

### 目标

定义客户端-服务器-Worker 之间的消息协议。

### 交付物

1. `src/protocol/` 模块
2. 协议测试
3. 协议文档

### 任务列表

#### M2.1: 定义消息类型

- **目标**：定义所有协议消息类型
- **输入**：参考项目 `lan_client.py`
- **输出**：
  - `src/protocol/messages.py`
  - `src/protocol/constants.py`
- **依赖**：M1.1
- **验收标准**：
  - 消息类型定义完整
  - 类型注解清晰
  - 单元测试通过
- **测试方式**：`tests/unit/test_protocol.py`

#### M2.2: 实现序列化

- **目标**：实现 JSON 序列化/反序列化
- **输入**：M2.1 的消息类型
- **输出**：
  - `src/protocol/serializer.py`
- **依赖**：M2.1
- **验收标准**：
  - 序列化正确
  - 反序列化正确
  - 错误处理完善
  - 单元测试通过
- **测试方式**：`tests/unit/test_serializer.py`

#### M2.3: 实现能力协商

- **目标**：实现客户端-服务器能力协商
- **输入**：M2.1 的消息类型
- **输出**：
  - `src/protocol/capabilities.py`
- **依赖**：M2.1
- **验收标准**：
  - 能力协商逻辑正确
  - 不兼容时正确拒绝
  - 单元测试通过
- **测试方式**：`tests/unit/test_capabilities.py`

#### M2.4: 编写协议文档

- **目标**：编写协议设计文档
- **输入**：M2.1-M2.3 的实现
- **输出**：
  - `docs/design/protocol.md`
- **依赖**：M2.1-M2.3
- **验收标准**：
  - 文档包含所有消息类型
  - 文档包含示例
  - 文档清晰易懂
- **测试方式**：文档评审

### 验收标准（里程碑）

- 协议定义完整
- 序列化/反序列化正确
- 能力协商可用
- 单元测试通过

### 测试方式

- `pytest tests/unit/test_protocol.py tests/unit/test_serializer.py`

### 风险

- 消息格式设计不当
- 性能问题（JSON 序列化）

---

## M3: sim-worker 权威服务器循环

### 目标

实现权威服务器，运行 30 Hz 世界 tick。

### 交付物

1. `src/sim_worker/` 模块
2. 服务器测试
3. 房间管理

### 任务列表

#### M3.1: 实现 TCP 服务器

- **目标**：实现 TCP 服务器骨架
- **输入**：参考项目 `lan_battle_server.py`
- **输出**：
  - `src/sim_worker/main.py`
  - `src/sim_worker/server.py`
- **依赖**：M2.1-M2.3
- **验收标准**：
  - 服务器可启动
  - 客户端可连接
  - 消息可收发
  - 集成测试通过
- **测试方式**：`tests/integration/test_server.py`

#### M3.2: 实现世界 tick

- **目标**：实现 30 Hz 世界 tick 循环
- **输入**：M3.1 的服务器
- **输出**：
  - `src/sim_worker/tick.py`
- **依赖**：M3.1
- **验收标准**：
  - tick 频率正确（30 Hz）
  - tick 循环稳定
  - 单元测试通过
- **测试方式**：`tests/unit/test_tick.py`

#### M3.3: 实现房间管理

- **目标**：实现房间/大厅管理
- **输入**：M3.1 的服务器
- **输出**：
  - `src/sim_worker/room/room.py`
  - `src/sim_worker/room/lobby.py`
- **依赖**：M3.1
- **验收标准**：
  - 房间创建/加入/离开正常
  - 队伍分配正确
  - 单元测试通过
- **测试方式**：`tests/unit/test_room.py`

#### M3.4: 实现状态快照

- **目标**：实现 15 Hz 状态快照广播
- **输入**：M3.2 的 tick
- **输出**：
  - `src/sim_worker/state/snapshot.py`
- **依赖**：M3.2
- **验收标准**：
  - 快照频率正确（15 Hz）
  - 快照数据完整
  - 单元测试通过
- **测试方式**：`tests/unit/test_snapshot.py`

### 验收标准（里程碑）

- 服务器可启动
- 30 Hz tick 循环稳定
- 房间管理可用
- 快照广播正常

### 测试方式

- `pytest tests/integration/test_server.py`

### 风险

- tick 循环性能
- 并发处理

---

## M4: 薄客户端补丁

### 目标

实现薄客户端，连接服务器，接收快照，发送输入。

### 交付物

1. `src/client/` 模块
2. 客户端测试
3. BigWorld hook

### 任务列表

#### M4.1: 实现客户端网络层

- **目标**：实现 TCP 客户端
- **输入**：参考项目 `lan_client.py`
- **输出**：
  - `src/client/network/client.py`
  - `src/client/network/connection.py`
- **依赖**：M2.1-M2.3
- **验收标准**：
  - 客户端可连接服务器
  - 消息可收发
  - 集成测试通过
- **测试方式**：`tests/integration/test_client.py`

#### M4.2: 实现客户端预测

- **目标**：实现本地玩家预测和远程插值
- **输入**：参考项目 `snapshot_sync.py`
- **输出**：
  - `src/client/prediction/local_player.py`
  - `src/client/prediction/interpolation.py`
- **依赖**：M4.1
- **验收标准**：
  - 本地玩家预测正确
  - 远程插值平滑
  - 单元测试通过
- **测试方式**：`tests/unit/test_prediction.py`

#### M4.3: 实现 BigWorld Hook

- **目标**：实现 BigWorld hook 系统
- **输入**：Offline2.3.1.2 `hooks.py` + 参考项目
- **输出**：
  - `src/client/hooks/avatar.py`
  - `src/client/hooks/vehicle.py`
  - `src/client/hooks/account.py`
- **依赖**：M1.2
- **验收标准**：
  - Hook 可安装
  - Hook 可触发
  - 集成测试通过
- **测试方式**：`tests/integration/test_hooks.py`

#### M4.4: 实现客户端入口

- **目标**：实现 BigWorld mod 入口和 bootstrap
- **输入**：M4.1-M4.3
- **输出**：
  - `src/client/mod_entry.py`
  - `src/client/bootstrap.py`
  - `src/client/session.py`
- **依赖**：M4.1-M4.3
- **验收标准**：
  - mod 可加载
  - bootstrap 可初始化
  - 会话管理正常
- **测试方式**：手动加载 mod 验证

### 验收标准（里程碑）

- 客户端可连接服务器
- 预测和插值正常
- BigWorld hook 可用
- mod 可加载

### 测试方式

- `pytest tests/integration/test_client.py`

### 风险

- BigWorld API 变化
- Python 2.7 限制
- 预测精度

---

## M5: 命令行启动器与部署

### 目标

实现命令行启动器，自动化部署到 res_mods。

### 交付物

1. `src/launcher/` 模块
2. `src/deploy/` 模块
3. 启动器测试

### 任务列表

#### M5.1: 实现部署脚本

- **目标**：实现 py → pyc 编译和部署
- **输入**：`src/client/` 模块
- **输出**：
  - `src/deploy/build.py`
  - `src/deploy/install.py`
  - `src/deploy/templates/config.json`
- **依赖**：M4.4
- **验收标准**：
  - py → pyc 编译正确
  - 部署到 res_mods 正确
  - 配置文件生成正确
  - 集成测试通过
- **测试方式**：`tests/integration/test_deploy.py`

#### M5.2: 实现启动器

- **目标**：实现命令行启动器
- **输入**：M5.1 的部署脚本
- **输出**：
  - `src/launcher/main.py`
  - `src/launcher/args.py`
  - `src/launcher/deploy.py`
  - `src/launcher/process.py`
- **依赖**：M5.1
- **验收标准**：
  - 命令行参数解析正确
  - 部署命令可用
  - 启动命令可用
  - 集成测试通过
- **测试方式**：`tests/integration/test_launcher.py`

#### M5.3: 编写使用文档

- **目标**：编写启动器使用文档
- **输入**：M5.2 的启动器
- **输出**：
  - `docs/design/launcher.md`
- **依赖**：M5.2
- **验收标准**：
  - 文档包含所有命令
  - 文档包含示例
  - 文档清晰易懂
- **测试方式**：文档评审

### 验收标准（里程碑）

- 部署脚本可用
- 启动器可用
- 文档完整

### 测试方式

- `pytest tests/integration/test_launcher.py`

### 风险

- pyc magic number 兼容性
- 部署路径问题

---

## M6: 基础同步（进入战斗、移动、炮塔）

### 目标

实现基础同步：进入战斗、移动、炮塔。

### 交付物

1. 战斗进入流程
2. 移动同步
3. 炮塔同步

### 任务列表

#### M6.1: 实现战斗进入流程

- **目标**：实现从车库到战斗的完整流程
- **输入**：
  - Offline2.3.1.2 `battle.py`
  - 参考项目 `lan_session.py`
- **输出**：
  - `src/sim_worker/battle/runtime.py`
  - `src/client/ui/waiting_room.py`
- **依赖**：M3.3, M4.4
- **验收标准**：
  - 可从车库进入战斗
  - 等待房间正常
  - 战斗开始正常
  - 集成测试通过
- **测试方式**：`tests/integration/test_battle_enter.py`

#### M6.2: 实现移动同步

- **目标**：实现车辆移动同步
- **输入**：Offline2.3.1.2 `drive.py`
- **输出**：
  - `src/sim_worker/battle/movement.py`
  - `src/client/prediction/local_player.py`
- **依赖**：M6.1
- **验收标准**：
  - 移动权威在服务器
  - 本地玩家预测正常
  - 远程车辆插值正常
  - 集成测试通过
- **测试方式**：`tests/integration/test_movement_sync.py`

#### M6.3: 实现炮塔同步

- **目标**：实现炮塔旋转同步
- **输入**：Offline2.3.1.2 `turret.py`
- **输出**：
  - `src/sim_worker/battle/turret.py`
  - `src/client/render/turret.py`
- **依赖**：M6.2
- **验收标准**：
  - 炮塔权威在服务器
  - 炮塔旋转平滑
  - 集成测试通过
- **测试方式**：`tests/integration/test_turret_sync.py`

### 验收标准（里程碑）

- 两个客户端可进入同一场战斗
- 移动同步正常
- 炮塔同步正常

### 测试方式

- `pytest tests/integration/test_battle_enter.py test_movement_sync.py test_turret_sync.py`

### 风险

- 移动物理精度
- 网络延迟影响

---

## M7: 战斗同步（开火、命中、伤害、死亡）

### 目标

实现战斗同步：开火、命中、伤害、死亡。

### 交付物

1. 开火同步
2. 命中同步
3. 伤害同步
4. 死亡同步

### 任务列表

#### M7.1: 实现开火同步

- **目标**：实现开火同步
- **输入**：Offline2.3.1.2 `shooting.py`
- **输出**：
  - `src/sim_worker/battle/shooting.py`
  - `src/client/network/client.py`（fire_intent）
- **依赖**：M6.3
- **验收标准**：
  - 开火权威在服务器
  - 弹道轨迹正确
  - 集成测试通过
- **测试方式**：`tests/integration/test_shooting.py`

#### M7.2: 实现命中同步

- **目标**：实现命中判定同步
- **输入**：Offline2.3.1.2 `shooting.py`, `armour.py`
- **输出**：
  - `src/sim_worker/battle/damage.py`
- **依赖**：M7.1
- **验收标准**：
  - 命中判定权威在服务器
  - 穿深计算正确
  - 集成测试通过
- **测试方式**：`tests/integration/test_hit.py`

#### M7.3: 实现伤害同步

- **目标**：实现伤害应用同步
- **输入**：M7.2 的命中判定
- **输出**：
  - `src/sim_worker/battle/damage.py`
- **依赖**：M7.2
- **验收标准**：
  - 伤害权威在服务器
  - 血量变化正确
  - 集成测试通过
- **测试方式**：`tests/integration/test_damage.py`

#### M7.4: 实现死亡同步

- **目标**：实现死亡判定同步
- **输入**：M7.3 的伤害应用
- **输出**：
  - `src/sim_worker/battle/damage.py`
- **依赖**：M7.3
- **验收标准**：
  - 死亡判定权威在服务器
  - 残骸呈现正确
  - 集成测试通过
- **测试方式**：`tests/integration/test_death.py`

### 验收标准（里程碑）

- 开火同步正常
- 命中同步正常
- 伤害同步正常
- 死亡同步正常

### 测试方式

- `pytest tests/integration/test_shooting.py test_hit.py test_damage.py test_death.py`

### 风险

- 命中判定精度
- 伤害计算复杂度

---

## M8: 断线重连

### 目标

实现断线重连功能。

### 交付物

1. 断线检测
2. 重连逻辑
3. 状态恢复

### 任务列表

#### M8.1: 实现断线检测

- **目标**：实现网络断线检测
- **输入**：M4.1 的客户端网络层
- **输出**：
  - `src/client/network/reconnect.py`
- **依赖**：M4.1
- **验收标准**：
  - 断线可检测
  - 心跳机制正常
  - 单元测试通过
- **测试方式**：`tests/unit/test_reconnect.py`

#### M8.2: 实现重连逻辑

- **目标**：实现自动重连
- **输入**：M8.1 的断线检测
- **输出**：
  - `src/client/network/reconnect.py`
- **依赖**：M8.1
- **验收标准**：
  - 自动重连正常
  - 状态恢复正确
  - 集成测试通过
- **测试方式**：`tests/integration/test_reconnect.py`

#### M8.3: 实现服务器端重连支持

- **目标**：实现服务器端重连支持
- **输入**：M8.2 的重连逻辑
- **输出**：
  - `src/sim_worker/room/room.py`
- **依赖**：M8.2
- **验收标准**：
  - 服务器接受重连
  - 状态恢复正确
  - 集成测试通过
- **测试方式**：`tests/integration/test_reconnect.py`

### 验收标准（里程碑）

- 断线可检测
- 自动重连正常
- 状态恢复正确

### 测试方式

- `pytest tests/integration/test_reconnect.py`

### 风险

- 状态恢复不完整
- 重连超时处理

---

## M9: 测试、文档、稳定性收尾

### 目标

完善测试、文档，确保稳定性。

### 交付物

1. 完整测试覆盖
2. 完整文档
3. 稳定性验证

### 任务列表

#### M9.1: 完善单元测试

- **目标**：提高单元测试覆盖率
- **输入**：所有模块
- **输出**：完善 `tests/unit/`
- **依赖**：M1-M8
- **验收标准**：
  - 单元测试覆盖率 > 80%
  - 所有测试通过
- **测试方式**：`pytest --cov`

#### M9.2: 完善集成测试

- **目标**：提高集成测试覆盖率
- **输入**：所有模块
- **输出**：完善 `tests/integration/`
- **依赖**：M1-M8
- **验收标准**：
  - 集成测试覆盖率 > 70%
  - 所有测试通过
- **测试方式**：`pytest --cov`

#### M9.3: 编写端到端测试

- **目标**：编写多客户端联机测试
- **输入**：所有模块
- **输出**：`tests/e2e/`
- **依赖**：M1-M8
- **验收标准**：
  - 多客户端联机测试通过
  - 权威状态一致性验证通过
- **测试方式**：`pytest tests/e2e/`

#### M9.4: 编写完整文档

- **目标**：编写完整项目文档
- **输入**：所有模块
- **输出**：
  - `README.md`
  - `docs/design/*.md`
  - `docs/user/*.md`
- **依赖**：M1-M8
- **验收标准**：
  - 文档完整
  - 文档清晰
  - 文档准确
- **测试方式**：文档评审

#### M9.5: 稳定性验证

- **目标**：验证长时间运行稳定性
- **输入**：所有模块
- **输出**：稳定性报告
- **依赖**：M1-M8
- **验收标准**：
  - 8 小时无崩溃
  - 内存无泄漏
  - 性能稳定
- **测试方式**：长时间运行测试

### 验收标准（里程碑）

- 测试覆盖完整
- 文档完整
- 稳定性验证通过

### 测试方式

- `pytest tests/`
- 长时间运行测试

### 风险

- 测试覆盖率不足
- 文档不完整
- 稳定性问题

---

## 里程碑依赖关系

```
M0 (多实例) ─────────────────────────────────┐
                                              │
M1 (SDK) ──→ M2 (协议) ──→ M3 (服务器) ──→ M6 (基础同步) ──→ M7 (战斗同步) ──→ M8 (重连) ──→ M9 (收尾)
                │              │                    │
                └──────────────┼────────────────────┘
                               │
M4 (客户端) ←──────────────────┘
     │
     └──→ M5 (启动器)
```

**关键路径**：M1 → M2 → M3 → M6 → M7 → M8 → M9

**并行任务**：
- M0（多实例）可与其他任务并行
- M4（客户端）可与 M3（服务器）并行
- M5（启动器）可与 M6-M8 并行
