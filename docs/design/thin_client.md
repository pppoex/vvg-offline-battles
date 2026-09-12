# 薄客户端设计（M4）

> PROTOCOL_VERSION = 5 · 默认端口 28782 · 客户端 Python 2.7（仅标准库）

## 1. 目标

M4 交付可连接 sim-worker 的薄客户端骨架：

- TCP + JSON lines（**完全复用** `src/protocol`，不另起协议）
- `hello` → `welcome` / `error`；`roster` / `snapshot` / `ping` / `input`
- BigWorld mod 入口（.pyc，Python 2.7）
- 客户端预测与插值**占位**（M6 完善）
- 集成测试对接真实 `GameServer`

运动积分权威、射击、完整 UI、自动重连不在 M4 范围。

## 2. 模块

| 路径 | 职责 |
|---|---|
| `src/client/mod_vvg_client.py` | BigWorld mod 入口（`init` / `fini`） |
| `src/client/vvg_client/bootstrap.py` | 路径、`sdk.config`、会话创建、hook 安装 |
| `src/client/vvg_client/session.py` | `ClientSession`：网络 + 预测粘合 |
| `src/client/vvg_client/network/connection.py` | `TcpLineConnection`：socket + LineDecoder + 队列 |
| `src/client/vvg_client/network/client.py` | `BattleClient`：协议会话与出站 API |
| `src/client/vvg_client/network/reconnect.py` | `ReconnectPolicy`（M8 接线） |
| `src/client/vvg_client/prediction/local_player.py` | 本地死区预测占位 |
| `src/client/vvg_client/prediction/interpolation.py` | 快照环形缓冲 + 插值占位 |
| `src/client/vvg_client/hooks/bigworld_hooks.py` | BigWorld `addCallback` 帧循环（无 BigWorld 时跳过） |
| `src/deploy/install_client.py` | 部署到 res_mods + Py2.7 编译 .pyc |
| `tests/unit/test_client_network.py` | 网络 / 预测 / 策略单测 |
| `tests/integration/test_client.py` | 对接 `sim_worker.GameServer` |

## 3. 连接流程

```
BattleClient                      sim-worker
  | --- TCP connect -------------> |
  | --- hello（首条） -------------> |
  | <--- welcome ------------------ |
  | <--- roster -------------------- |
  | --- start_battle / input -----> |
  | <--- battle_start / live ------ |
  | <--- snapshot (15 Hz) --------- |
  | --- ping --------------------> |
  | <--- pong --------------------- |
```

环境变量（启动器设置，M5 接线）：

| 变量 | 说明 |
|---|---|
| `VVG_PLAYER_NAME` | 玩家名 |
| `VVG_PLAYER_VEHICLE` | 车辆 compact descr |
| `VVG_SERVER_HOST` / `VVG_SERVER_PORT` | 服务器地址 |
| `VVG_CLIENT_MODE` | `player` / `simulation_worker` |

未设置时回落 `sdk.config`（`127.0.0.1:28782`）与默认名 `Player` / `ussr:R05_LT`。

## 4. 线程与 pump

- 接收线程：`TcpLineConnection` 内部，解码后入 pending 队列。
- 出站：`send_message` 持 send 锁 `sendall`。
- 主线程（BigWorld callback 或测试）调用 `ClientSession.tick()` / `BattleClient.pump()`。
- 有界队列：溢出时优先丢弃旧 `snapshot`，状态屏障与 `pong` 不丢。

## 5. 预测 / 插值（占位）

- `LocalPlayer`：welcome.spawn 播种；固定步长死区；权威行硬校正。
- `SnapshotBuffer`：保留最近 N 帧；按延迟采样并对 remote pose 做最短角混合。
- M6 将迁入 Offline `drive` 相关权威积分，并收紧预测误差处理。

## 6. 部署

```powershell
# 从工作区根目录
python src/deploy/install_client.py
# 或指定游戏根
python src/deploy/install_client.py --game-root "D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2"
```

安装到 `res_mods/2.3.1.2/scripts/client/gui/mods/`：

- `mod_vvg_client.py` + `.pyc`
- `vvg_client/` 全量 `.py` + `.pyc`
- `protocol/` 全量 `.py` + `.pyc`（vendored）
- `sdk/` 全量 `.py` + `.pyc`（供 config / hooks / log）

游戏只加载 .pyc；magic 必须为 `62211`（由 `install_multiclient.find_python27` / `compile_pyc` 保证）。

## 7. 测试

```bash
# 单测 + 集成
python -m pytest tests/unit tests/integration -q

# 仅客户端相关
python -m pytest tests/unit/test_client_network.py tests/integration/test_client.py -q
```

## 8. M4 已知简化

1. 无自动重连（策略已就绪，M8 接线）。
2. 预测为常系数占位，非 Offline 物理。
3. 无车辆实体绑定 / UI（M6+ 与 BigWorld Avatar 对接）。
4. `leave_battle` 服务器侧仍整房回 waiting（M3 行为）。
5. 真机游戏内验证依赖日志；宿主无法加载 Py2.7 pyd。

## 9. 与 M3 的边界

- 客户端不实现权威模拟；只发意图（input / 控制）并应用快照。
- 消息 builder 全部来自 `protocol.messages`；禁止本地 envelope 分叉。
