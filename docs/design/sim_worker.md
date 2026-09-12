# sim-worker 服务器设计（M3）

> PROTOCOL_VERSION = 5 · 默认端口 28782 · 30 Hz tick · 15 Hz snapshot

## 1. 目标

M3 交付权威服务器**骨架**：

- TCP JSON lines 接入（复用 `src/protocol`，不另起协议）
- `hello` → 能力协商 → `welcome` / `error`
- 大厅 roster、自动分队、选队/换车
- host `start_battle` → `battle_start` / `battle_live`
- 30 Hz 世界 tick；战斗相位下 15 Hz `snapshot`
- `ping` / `pong`、`leave` / `leave_battle`

运动积分、射击、Bot、重连不在 M3 范围（M6–M8）。

## 2. 模块

| 路径 | 职责 |
|---|---|
| `src/sim_worker/main.py` | CLI 入口 |
| `src/sim_worker/server.py` | TCP + 握手 + 分发 + 广播（`GameServer` / `GameWorld`） |
| `src/sim_worker/session.py` | 玩家会话与占位姿态 |
| `src/sim_worker/tick.py` | `TickLoop` 固定步进 |
| `src/sim_worker/room/lobby.py` | 分队、出生点占位 |
| `src/sim_worker/room/room.py` | 房间相位、成员、轻量快照 |
| `tests/integration/test_server.py` | 集成测试 |
| `tests/integration/client_util.py` | 测试客户端 |

## 3. 连接流程

```
Client                         Server
  | --- hello ------------------> |
  | <--- welcome ----------------- |
  | <--- roster（本人） ------------ |
  | <--- roster（他人广播） --------- |
  | --- ping/select/start/input -> |
  | <--- pong/roster/snapshot ---- |
```

握手失败：`{"type":"error","code":...,"message":...}`（code 对齐 protocol.md）。

## 4. Tick 与快照

- `TickLoop`：`interval = 1/tick_hz`；落后时连续消费欠账 tick。
- `snapshot_ticks = max(1, round(tick_hz / snapshot_hz))` → 默认每 2 tick。
- 仅 `phase == battle` 时广播 snapshot。
- 快照 payload（`lean_snapshot_v1` 占位）：

```json
{"players":[{"id":1,"name":"...","vehicle":"...","team":1,
  "pos":[x,y,z],"yaw":0,"aim_yaw":0,"gun_pitch":0,"speed":0}]}
```

M6 再收紧 schema 并接入 `sdk.math` 权威积分。

## 5. 线程模型

- 每个 TCP 连接一个 handler 线程（`ThreadingMixIn`）。
- `GameWorld.lock`（RLock）保护房间与会话表。
- Tick 在独立线程；测试可用 `GameServer.run_ticks` 无 sleep 推进。

## 6. 启动

```powershell
# 开发
$env:PYTHONPATH = "src"
python -m sim_worker.main --host 127.0.0.1 --port 28782 --map training

# 测试
python -m pytest tests/integration/test_server.py -q
```

## 7. M3 已知简化

1. 单房间、无地图池。
2. `input` 只写会话姿态，不积分。
3. `leave_battle` 将整房回到 `waiting`（多人精细退出在后续里程碑）。
4. 出生点为队伍对称占位，非真实地图点。
5. Bot / simulation_worker 角色未实现（OPEN_QUESTIONS：基础 Bot 建议方案）。
