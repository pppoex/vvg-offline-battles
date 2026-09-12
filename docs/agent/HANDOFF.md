# HANDOFF.md

> 交接记录 — 给下一个 Agent 的最重要文件

## 当前阶段

**M3 完成：sim-worker 权威服务器骨架，unit+integration 全绿**

M0 多实例、M1 SDK、M2 协议、M3 服务器骨架均已完成。

远程仓库：https://github.com/pppoex/vvg-offline-battles

## 最后 commit

- **hash**: `49fec39`
- **message**: `docs(agent): M3 完成交接与里程碑更新 [TASK-M3]`
- **业务 commit**: `de5dd79` `feat(sim_worker): 实现 TCP 服务器骨架与 30Hz tick [TASK-M3]`
- **已推送**: `master` → `origin/main`

## 已完成

1. **TASK-000 ~ TASK-007**: 初始化与第一阶段只读分析
2. **TASK-M0 ~ M0.F**: 多实例限制解除（双开验证通过）
3. **TASK-M1**: 项目骨架与 SDK 抽取
4. **TASK-M2**: 协议与序列化
5. **TASK-M3**: sim-worker 权威服务器骨架
   - `src/sim_worker/main.py` — CLI
   - `src/sim_worker/server.py` — TCP + 握手 + 分发 + 广播
   - `src/sim_worker/session.py` — 会话
   - `src/sim_worker/tick.py` — 30 Hz TickLoop
   - `src/sim_worker/room/lobby.py` / `room.py` — 大厅与房间
   - `tests/integration/test_server.py` + `client_util.py`
   - `docs/design/sim_worker.md`
   - 验证：`python -m pytest tests/unit tests/integration -q` 全绿

## 未完成

1. **M4: 薄客户端补丁**（下一个里程碑）
2. **M5-M9**: 后续里程碑
3. 运动积分 / 射击 / Bot / 重连（M6-M8，M3 仅骨架）
4. **WGC cleanup thunk x64 RVA 逆向**（低优先级）
5. **install_atmosphere_owner_guard**（0.9.22 专属，不阻塞）

## 正在处理

- M3 刚完成；等待进入 M4（薄客户端）

## 下一步建议

进入 **M4: 薄客户端补丁**：

1. `src/client/network/` — 客户端 TCP + LineDecoder
2. 复用 `src/protocol` 发 hello / 收 welcome / snapshot
3. BigWorld hook 与 mod 加载（.pyc / Python 2.7）
4. 客户端预测占位（M6 再完善）
5. 集成测试 `tests/integration/test_client.py`
6. 注意：客户端路径必须 2/3 兼容且仅标准库

## 关键文件

### M3（本轮）

- `src/sim_worker/server.py`
- `src/sim_worker/tick.py`
- `src/sim_worker/room/room.py`
- `src/sim_worker/room/lobby.py`
- `src/sim_worker/session.py`
- `src/sim_worker/main.py`
- `tests/integration/test_server.py`
- `docs/design/sim_worker.md`

### M2

- `src/protocol/**`
- `docs/design/protocol.md`

### M1

- `src/sdk/**`
- `pyproject.toml`

### M0

- `src/multiclient/**`
- `src/client/mod_vvg_instance_guard.py`

### 分析 / 设计文档

- `docs/design/protocol.md`
- `docs/design/sim_worker.md`
- `docs/analysis/05-migration-and-sdk-plan.md`
- `docs/agent/MILESTONES.md`

### 源项目（只读）

- `D:\Projects\Offline2.3.1.2`
- `D:\Projects\wot-offline-battles`
- `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2`

## 关键发现

### M3 服务器

- 协议层完全复用 `protocol.messages` builder，禁止另起 envelope
- Tick 与 TCP 分线程；房间状态用 `RLock`
- 快照仅在 `phase==battle` 且每 `tick_hz/snapshot_hz` tick 广播
- 新玩家：先 `welcome` 再给本人 `roster`，再广播给他人
- `leave_battle` 简化为整房回 waiting（后续细化）

### 协议 / SDK（仍有效）

- PROTOCOL_VERSION=5；端口 28782；必选能力 `core_session_v1`
- 客户端 Python 2.7；服务器 Python 3；protocol/sdk 双兼容
- 主互斥体 `WOT_STARTUP_MUTEX`；.pyc magic=62211

## 风险

1. M4 客户端若改变消息语义，M3 房间逻辑需小幅适配
2. 真实战斗逻辑（drive/shooting）迁入时需拆分 Offline 大文件
3. 宿主无法加载 Py2.7 pyd — 游戏内验证以日志为准

## 待用户确认

1. ~~M0 真机双开~~ — 已通过
2. ~~M1 / M2~~ — 已完成
3. ~~M3~~ — 骨架完成
4. 是否继续 **M4（薄客户端补丁）**
5. Bot AI 范围 / 单人模式：DECISIONS 已倾向「基础 Bot」「单人也启 sim-worker」，M6 前最终确认即可

## 禁止事项提醒

- 禁止修改 `D:\Projects\Offline2.3.1.2`
- 禁止修改 `D:\Projects\wot-offline-battles`
- 禁止修改游戏安装目录、exe、dll、核心资源
- 禁止无证据编造 API、文件、协议
- 禁止把大量代码写进单文件
- 禁止跳过测试和文档
