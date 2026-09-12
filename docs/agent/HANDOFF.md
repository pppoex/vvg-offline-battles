# HANDOFF.md

> 交接记录 — 给下一个 Agent 的最重要文件

## 当前阶段

**M2 完成：协议与序列化，单测全绿**

M0 多实例、M1 SDK 骨架、M2 协议层均已完成。

远程仓库：https://github.com/pppoex/vvg-offline-battles

## 最后 commit

- **hash**: `59cf674`
- **message**: `docs(agent): M2 收尾回填 commit hash [TASK-M2]`
- **业务 commit**: `2ae17fe` `feat(protocol): 实现 JSON lines 协议层与能力协商 [TASK-M2]`
- **已推送**: `master` → `origin/main`

## 已完成

1. **TASK-000 ~ TASK-007**: 初始化与第一阶段只读分析
2. **TASK-M0 ~ M0.F**: 多实例限制解除（双开验证通过，已推 GitHub）
3. **TASK-M1**: 项目骨架与 SDK 抽取
4. **TASK-M2**: 协议与序列化
   - `src/protocol/__init__.py` — 包入口
   - `src/protocol/constants.py` — PROTOCOL_VERSION=5、消息类型、限制、端口 28782
   - `src/protocol/messages.py` — hello/welcome/input/roster/snapshot 等 builder + 校验
   - `src/protocol/serializer.py` — JSON lines encode/decode + LineDecoder 粘包
   - `src/protocol/capabilities.py` — 能力名与 negotiate()
   - `tests/unit/test_protocol.py` / `test_serializer.py`
   - `docs/design/protocol.md` — 协议文档
   - 验证：`python -m pytest tests/unit -q` 全绿；`D:\Python27` 下 protocol 可编译

## 未完成

1. **M3: sim-worker 权威服务器**（下一个里程碑）
2. **M4: 薄客户端补丁**
3. **M5-M9**: 后续里程碑
4. **WGC cleanup thunk x64 RVA 逆向**（低优先级，句柄枚举方案已可用）
5. **install_atmosphere_owner_guard**（0.9.22 专属，不阻塞）

## 正在处理

- M2 刚完成；等待进入 M3

## 下一步建议

进入 **M3: sim-worker 权威服务器**：

1. 创建 `src/sim_worker/`：`main.py` / `server.py` / `tick.py` / `room/`
2. TCP 服务器收 hello → 能力协商 → welcome；广播 roster
3. 30 Hz tick 循环（`SERVER_TICK_HZ`）；快照 15 Hz
4. 复用 `src/protocol` 的 serializer / messages
5. 集成测试 `tests/integration/test_server.py`
6. 参考 `server/lan_battle_server.py` 架构 + `docs/analysis/05-migration-and-sdk-plan.md` §5.2

## 关键文件

### M2（本轮）

- `src/protocol/constants.py`
- `src/protocol/messages.py`
- `src/protocol/serializer.py`
- `src/protocol/capabilities.py`
- `tests/unit/test_protocol.py`
- `tests/unit/test_serializer.py`
- `docs/design/protocol.md`

### M1

- `pyproject.toml`
- `src/sdk/hooks.py`
- `src/sdk/log.py`
- `src/sdk/config.py`
- `src/sdk/math/vector.py`
- `src/sdk/math/matrix.py`
- `tests/unit/test_sdk_*.py`

### M0

- `src/multiclient/native/instance_guard.c`
- `src/multiclient/native/worker_starter.c`
- `src/multiclient/instance_guard.py`
- `src/client/mod_vvg_instance_guard.py`
- `src/client/vvg_instance_guard/bootstrap.py`
- `src/deploy/install_multiclient.py`

### 分析 / 设计文档

- `docs/design/protocol.md` — M2 协议规范
- `docs/analysis/05-migration-and-sdk-plan.md` — 迁移计划
- `docs/analysis/multiclient-research.md` — M0 逆向报告
- `docs/agent/MILESTONES.md` — 里程碑总览

### 源项目（只读）

- `D:\Projects\Offline2.3.1.2`
- `D:\Projects\wot-offline-battles`
- `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2`

## 关键发现

### 协议（M2）

- 参考项目 v5：JSON lines、紧凑分隔符、hello 必须为首条消息
- ping/pong 携带 `seq` + `client_time` / `server_time`
- 能力列表：list[str]，≤32 项，必选 `core_session_v1`
- 服务器错误：`{"type":"error","code":...,"message":...}`
- 状态屏障与 snapshot 分离，避免快照冲掉 roster/welcome

### SDK（M1，仍有效）

- Offline hooks/log 有 Decompyle artifact，SDK 已重写
- config 不复制 Offline 882 行单机参数
- 欧拉角 R = Ry·Rx·Rz；pitch 向上抬为负

### 运行时

- 宿主 Python 3.14；游戏内嵌 Python 2.7 无 `_ctypes`
- SDK / protocol 须 2/3 兼容
- 主互斥体：`WOT_STARTUP_MUTEX`；.pyc magic=62211

## 风险

1. snapshot.payload / events schema 在 M3 收紧时若破坏 envelope，M4 适配成本高 — 尽量只增字段
2. sim-worker 迁移 Offline 大文件时仍需去 BigWorld 依赖
3. 宿主无法加载 Py2.7 pyd 作扩展 — 真机验证以游戏日志为准

## 待用户确认

1. ~~M0 真机双开~~ — 已通过
2. ~~继续 M1~~ — 已完成
3. ~~继续 M2~~ — 已完成
4. 是否继续 **M3（sim-worker 权威服务器）**

## 禁止事项提醒

- 禁止修改 `D:\Projects\Offline2.3.1.2`
- 禁止修改 `D:\Projects\wot-offline-battles`
- 禁止修改游戏安装目录、exe、dll、核心资源
- 禁止无证据编造 API、文件、协议
- 禁止把大量代码写进单文件
- 禁止跳过测试和文档
