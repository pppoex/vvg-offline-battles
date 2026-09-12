# 协议设计 — vvg-offline-battles

> 版本：PROTOCOL_VERSION = 5  
> 传输：JSON lines over TCP（UTF-8，newline-delimited）  
> 默认端口：28782（与 `sdk/config.py` 的 `SERVER_PORT` 对齐）  
> 实现：`src/protocol/`

## 1. 设计原则

1. **对齐 0.9.22 参考协议语义**：消息名、hello/welcome 握手、能力协商、ping/pong 保持一致，降低 M3/M4 适配成本。
2. **客户端 / 服务器共用**：`src/protocol/**` 保持 Python 2/3 双兼容（游戏内嵌 2.7，sim-worker 用 3.x）。
3. **服务器权威**：客户端只发送意图（hello / input / 控制命令）；世界状态、命中、伤害均由服务器广播。
4. **紧凑 JSON**：`json.dumps(..., separators=(',', ':'), ensure_ascii=True)` + 单行 `\n`。
5. **有界消息**：单条 ≤ 256 KiB；接收缓冲 ≤ 512 KiB。

## 2. 模块结构

| 文件 | 职责 |
|---|---|
| `constants.py` | 版本、消息类型集合、限制、默认地址 |
| `messages.py` | 消息 builder + 轻量校验 |
| `serializer.py` | encode/decode + `LineDecoder` 粘包处理 |
| `capabilities.py` | 能力名、规范化、协商 |

## 3. 线上格式

```
<utf8-json-object>\n
```

- 编码：UTF-8，`ensure_ascii=True`（非 ASCII 转 `\uXXXX`）
- 分隔：单字节 `0x0A`，消息体不含裸换行
- 首条消息：客户端 **必须** 先发 `hello`；服务器未收到合法 hello 前不接受其它类型

示例（player hello）：

```json
{"type":"hello","protocol":5,"client_build":"wot-2.3.1.2-vvg","capabilities":["core_session_v1"],"role":"player","name":"Alice","vehicle":"ussr:R05_LT"}
```

## 4. 握手

```
Client                         Server
  | --- hello ------------------> |
  | <--- welcome ----------------- |   （成功）
  | <--- error(code=...) -------- |   （失败，随后可关连接）
  | --- ping / control ---------> |
  | <--- pong / roster ----------- |
```

### hello（client → server）

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | str | `"hello"` |
| `protocol` | int | 必须 = 5 |
| `client_build` | str | 构建标签 |
| `capabilities` | list[str] | 客户端能力 |
| `role` | str | `"player"` \| `"worker"` |
| `name` | str? | player 必填 |
| `vehicle` | str? | player 必填 |
| `account_key` | str? | 可选账号键 |
| `max_health` | int? | 可选 |
| `requested_team` | 1\|2? | 可选 |

worker hello **不**携带 vehicle / max_health 等玩家字段；可额外声明 `simulation_worker_v1`。

### welcome（server → client）

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | str | `"welcome"` |
| `protocol` | int | 服务器协议版本 |
| `player_id` | int | 分配的玩家 ID |
| `name` / `vehicle` | str | 回显身份 |
| `team` | 1\|2 | 分配队伍 |
| `map` | str | 当前地图 |
| `phase` | str | waiting / loading / battle / finished |
| `round_id` | int | 回合号 |
| `state_revision` | int | 状态修订号 |
| `capabilities` | list[str] | 服务器认可的客户端能力 |
| `server_capabilities` | list[str] | 服务器能力 |
| `host_player_id` | int? | 房主 |
| `spawn` | object? | 出生点 `{x,y,z,yaw}` |
| `server_time_ms` | int? | 服务器时钟 |

### error（server → client）

```json
{"type":"error","code":"protocol","message":"protocol mismatch"}
```

常见 code：`protocol` / `unsupported_role` / `unsupported_capabilities` / `invalid_hello` / `join_rejected`。

## 5. 消息类型

### 客户端 → 服务器

| type | 用途 | 关键字段 |
|---|---|---|
| `hello` | 握手 | 见上 |
| `leave` | 礼貌断开 | — |
| `leave_battle` | 退出当前回合（TCP 保持） | `round_id` |
| `start_battle` | host 开战 | `round_id`, `round_seconds?` |
| `select_vehicle` | 换车 | `vehicle`, `max_health?` |
| `select_team` | 选队 | `team` (0=auto,1,2) |
| `battle_ready` | 资源加载完成 | `round_id` |
| `input` | 驾驶/瞄准输入 | 见 §6 |
| `ping` | 保活 / RTT | `seq`, `client_time` |

### 服务器 → 客户端

| type | 用途 | 关键字段 |
|---|---|---|
| `welcome` | 握手接受 | 见上 |
| `roster` | 大厅/成员名单 | `phase`, `players`, `state_revision` |
| `battle_start` | 回合开始 | `round_id`, `map` |
| `battle_live` | 进入倒计时/战斗屏障 | `server_tick`, `timing` |
| `snapshot` | 权威世界快照 | `round_id`, `server_tick`, `payload` |
| `events` | 离散事件批 | `events[]` |
| `pong` | ping 回显 | `seq`, `server_time` |
| `start_denied` | 开战被拒 | `reason` |
| `team_denied` | 选队被拒 | `team`, `reason` |
| `error` | 致命错误 | `code`, `message` |

状态屏障类型（客户端须立即消费，不可被 snapshot 跳过）：
`welcome`, `roster`, `battle_start`, `battle_live`, `start_denied`, `team_denied`, `events`, `error`。

## 6. input 信封

M2 只定义核心字段；M6/M7 再扩展弹道与姿态细节。

| 字段 | 类型 | 约束 |
|---|---|---|
| `type` | str | `"input"` |
| `round_id` | int | ≥ 0 |
| `input_seq` | int | 单调递增，回合内有效 |
| `forward` | float | clamp 到 [-1, 1] |
| `turn` | float | clamp 到 [-1, 1] |
| `aim_yaw` | float | 弧度 |
| `gun_pitch` | float | \|p\| ≤ 1.2 |
| `fire_seq` | int | 开火意图序号 |
| `position` | [x,y,z]? | 世界坐标，有界 |
| `yaw` / `pitch` / `roll` | float? | 姿态，\|pitch/roll\| ≤ 0.61 |
| `speed` | float? | \|speed\| ≤ 200 |

## 7. 能力协商

- 能力名：短 ASCII 字符串（≤ 64 字符），列表 ≤ 32 项，去重。
- M2 必选：`core_session_v1`（双方 hello/welcome 都必须出现）。
- M2 默认客户端：`core_session_v1`
- M2 默认服务器：`core_session_v1`, `movement_sync_v1`, `lean_snapshot_v1`
- 未来能力（预留名）：
  - `movement_sync_v1` — M6 移动同步
  - `lean_snapshot_v1` — 精简快照清单
  - `fire_intent_v1` / `projectile_ledger_v1` — M7 射击
  - `simulation_worker_v1` — 权威 worker 角色
  - `reconnect_v1` — M8 重连

协商 API：`protocol.capabilities.negotiate(client_caps, server_caps)`  
返回 `{ok, client, server, shared, missing}`。

## 8. ping / pong

```
→ {"type":"ping","seq":N,"client_time":T}
← {"type":"pong","seq":N,"client_time":T,"server_time":S}
```

默认间隔 1.0s（`constants.PING_INTERVAL`）。RTT ≈ 收到 pong 的墙钟 − `client_time`（实现层可改用单调钟）。

## 9. 大小与安全边界

| 常量 | 值 |
|---|---|
| `MAX_MESSAGE_BYTES` | 262144 |
| `MAX_BUFFER_BYTES` | 524288 |
| `MAX_CAPABILITY_COUNT` | 32 |
| `MAX_TEAM_SIZE` | 15 |
| `MAX_ROUND_SECONDS` | 14400 |

不做反作弊，但 builder 校验数值范围，防止明显畸形输入进入权威模拟。

## 10. 与 sdk.config 对齐

| config 键 | protocol 常量 |
|---|---|
| `PROTOCOL_VERSION = 5` | `constants.PROTOCOL_VERSION` |
| `JSONLINES_DELIMITER = b'\n'` | `constants.JSONLINES_DELIMITER` |
| `SERVER_HOST` / `SERVER_PORT` | `DEFAULT_SERVER_HOST` / `DEFAULT_SERVER_PORT` |

单元测试 `test_protocol.py::ConstantsTests` 强制两端版本一致。

## 11. 测试

```bash
python -m pytest tests/unit/test_protocol.py tests/unit/test_serializer.py -q
# 或全量
python -m pytest tests/unit -q
```

覆盖：消息 builder、能力协商、round-trip、粘包/半包、超长拒绝、UTF-8 名、与 config 端口/版本对齐。

## 12. 后续里程碑扩展点

- **M3**：`snapshot.payload` 与 `events[].kind` 的 schema 收紧；room 管理用 `roster` / `start_battle` / `battle_live`
- **M4**：客户端网络层复用 `LineDecoder`；预测层消费 `snapshot`
- **M6/M7**：input 扩展字段、弹道事件类型名在 `constants` 增补，不破坏 v5 envelope
- **M8**：`reconnect_v1` + `account_key` 会话恢复
