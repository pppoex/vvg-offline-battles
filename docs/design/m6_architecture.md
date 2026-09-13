# M6 联机架构设计

> 基于 2026-09 与用户的多轮确认 · 对齐 0.9.22 三层权威模型 · PROTOCOL_VERSION = 5

## 1. 目标与范围

M6 交付**基础同步联机闭环**：

- 进入战斗（拦截 Offline 单机路径）
- 移动 / 炮塔同步
- 局域网多机
- 权威物理在独立游戏进程
- Web 状态页代替游戏内房间 UI
- 原地 Bot（无移动 AI）

**不在 M6 范围**：完整 Bot AI、开火/命中/伤害（M7）、断线重连（M8）、结果屏、完整车数据 profile 下发。

## 2. 进程拓扑（0.9.22 式三层）

```
可见玩家客户端 A/B  ──TCP JSON──►  sim-worker (Python3)
        ▲                              │
        │ snapshot 15Hz                │ 权威提案 / input 中继
        │                              ▼
        └────────────────────  隐藏权威游戏 Worker
                               (VVG_CLIENT_MODE=simulation_worker)
                               Offline battle 空间 · 不作为玩家
```

| 进程 | 职责 | 不做什么 |
|---|---|---|
| **可见玩家** | 输入、渲染、插值、本机 Web 状态页、尽早拦截 join | 不做权威物理 |
| **sim-worker** | 房间相位、host、中继、快照广播、车数据一致性校验 | 不跑游戏引擎物理 |
| **权威 Worker** | Offline battle 空间；移动/碰撞权威积分；原地 Bot；pose 提案 | 不作为玩家进入大厅战斗名单 |

数据路径（对齐 0.9.22）：

```
visible client → sim-worker → hidden worker → sim-worker → replicas
```

### 2.1 单机同路径

单人也启动：`sim-worker` + 权威 worker + 自己。不经 Offline 单机路径。

### 2.2 局域网

- sim-worker 监听 `0.0.0.0:28782`（或可配置）
- 固定主机；客户端 `VVG_SERVER_HOST` / Web 配置手填服务器 IP
- 不做 mDNS / 服务发现（M6）

## 3. 房间与 Web 状态页

### 3.1 设计原则

1. **不用游戏内房间 UI**（不做 Flash/原生 waiting room 移植）
2. Web **不在 sim-worker 进程内**；放在**每个玩家客户端侧**（本机 HTTP）
3. 点击车库「战斗」→ **尽早拦截** Offline `enterRandom` / joining 层 → 打开默认浏览器到本机 Web
4. Web 只做**状态页 + 开战**；控制经 TCP 转发到 sim-worker
5. **仅房主可开战**

### 3.2 本机 Web HTTP

| 项 | 约定 |
|---|---|
| 宿主 | 玩家客户端配套小 HTTP（游戏进程内线程或配套 helper；**非** sim-worker） |
| 地址 | `http://127.0.0.1:<web_port>/` |
| 端口 | 同机多开从 **18080** 起自动递增找空闲口；日志/环境变量写明实际端口 |
| 内容 | 服务器地址、地图、玩家列表/就绪、开战按钮（仅房主）、简要状态 |
| 控制 | HTTP handler → 已建立的 `vvg_client` / 协议会话 → sim-worker 消息 |

### 3.3 房主

- **最先成功接入 sim-worker 的 player** 成为 `host_player_id`
- 服务器在 roster / room 快照中下发 host
- Web 仅在 `is_room_host` 时展示可点的「开始战斗」

### 3.4 进入战斗时序

```
用户点击车库 Battle
  → 最早钩子拦截 Offline CMD_ENQUEUE / battle.enterRandom
  → 避免 joining 进度层卡死
  → 客户端确保已连 sim-worker（或提示填 IP / 连接）
  → 启动本机 Web + 浏览器打开状态页
  → 房主点「开始战斗」
  → sim-worker: start_battle
  → 权威 worker: 收到 start_battle 后 battle.enter 建 Offline 空间
  → battle_start / battle_live
  → 可见客户端进战斗；远端车用快照插值 + 0.9.22 呈现层
```

拦截实现落点（按「尽可能早」优先级）：

1. **首选**：车库 Battle 按钮 / lobby join 行为（类似 0.9.22 `lan_session.join`）
2. **兜底**：`fake_server._cmdEnqueueInBattleQueue` 立即应答并转联机，**禁止**调用 `battle.enterRandom`
3. 实现时以真机日志验证：不得出现 Offline joining 卡死

## 4. 权威 Worker

| 项 | 约定 |
|---|---|
| 角色 | `role=worker`，能力含 `simulation_worker_v1` |
| 何时进 battle | **仅在 start_battle 之后**创建 Offline battle 空间；平时停在连接/等待态 |
| 空间来源 | Offline `battle` 模块路径（地形/模型/碰撞）；**不是** Python 纯数学积分 |
| 玩家身份 | **不作为玩家**；私有 off-map Avatar / 合成身份，不进玩家 roster 语义 |
| Bot | M6 **原地 Bot**（出生后不动）；无寻路/射击 AI；AI 推后 |

Worker 与 sim-worker：

- Worker 作为 TCP 客户端连 sim-worker（M4 已有 role）
- 权威提案（pose / 后续 bot_state）经 sim-worker 中继或直连扩展（实现时按协议扩展，避免绕过服务器权威）

## 5. 可见客户端战斗呈现

| 项 | 约定 |
|---|---|
| 本地车 | 预测 + 服务器校正（既有 prediction 占位完善） |
| 远端车 | **移植 0.9.22 呈现层**（`entities/remote_vehicle` / `native_remote_vehicle` 思路，适配 2.3.1.2 API） |
| 插值 | 15 Hz snapshot → 环形缓冲 + 延迟插值 |
| 离开战斗 | `leave_battle` 回车库；结果屏后置 |

**禁止**：远端车走 Offline 自己的 `drive` 单机权威。

## 6. 地图 / 车辆 / 车数据

| 项 | M6 约定 |
|---|---|
| 地图 | **无白名单**；吃 Offline `ArenaType` / 现有几何名 |
| 车辆 | **无白名单**；车库当前选车 compact descr |
| 车数据同步 | **一致性校验**（compact descr / 关键属性哈希）；不一致则拒绝进同一房 / 不一致警报 |
| 完整 profile 下发 | **后置**（非 M6） |
| 资源包 | M6 **不传**地图/模型资源；假设同版本客户端本地数据一致 |

## 7. 协议扩展（相对 M3 骨架）

在 `src/protocol` 现有 v5 上扩展（仍 JSON lines）：

| 方向 | 消息（建议名） | 说明 |
|---|---|---|
| client → server | `ready` / `set_ready` | Web 就绪状态 |
| client → server | `start_battle` | 仅 host；服务器校验 |
| server → all | `host` / roster 扩展 | `host_player_id` |
| server → all | `map_change` / room meta | 当前地图 |
| client → server | `input`（增强） | 移动/炮塔意图字段收紧 |
| worker → server | 权威 pose 提案 | 具体名实现时定（如 `worker_pose`） |
| server → client | `snapshot`（收紧 schema） | pos/yaw/aim 等；对齐 lean_snapshot_v1 → 正式版 |
| client → server | `vehicle_hash`（hello 或 join 附带） | 车数据一致性 |

实现时更新 `docs/design/protocol.md`，避免只写在本文。

## 8. 模块落点（规划）

```
src/
  client/vvg_client/
    join_gate.py          # 尽早拦截 Offline battle 入口
    webui/                # 本机 HTTP 状态页（Py2 标准库 BaseHTTP）
    presentation/         # 移植/适配 0.9.22 远端车呈现
    prediction/           # 已有；完善插值
  sim_worker/
    room/                 # 扩展 host / ready / map
    relay/                # worker 提案中继与校验
  protocol/               # 消息扩展（2/3 兼容）
  deploy/                 # 客户端 web 端口/启动环境变量
```

禁止把逻辑堆进单文件；客户端路径 2/3 兼容、仅标准库。

## 9. 启动顺序（推荐）

```powershell
# 主机
python -m launcher server          # 监听 0.0.0.0:28782
python -m launcher worker --hide   # 权威游戏进程
python -m launcher player --name Alice

# 局域网加入者
# VVG_SERVER_HOST=<主机IP>
python -m launcher player --name Bob
```

主机玩家：进车库 → 点战斗 → 浏览器 Web → 点开战。

## 10. 验收标准（M6）

- [ ] 车库点战斗**不**进入 Offline 单机 battle / 不卡 joining（Phase2 代码就绪，待真机）
- [ ] 本机浏览器可打开 Web 状态页并看到服务器/地图/玩家（Phase2 代码就绪，待真机）
- [ ] 仅房主可点开战；开战后双方进同一战斗
- [ ] 双方可见彼此车辆移动与炮塔（插值呈现）
- [ ] 权威在 worker 游戏进程；玩家客户端不跑 Offline drive 权威
- [ ] 局域网第二台机器填 IP 可加入并同步
- [ ] 车数据不一致时被拒绝或明确报错
- [ ] leave_battle 可回车库
- [ ] 原地 Bot 可在名单中（可选：可生成原地 Bot）
- [ ] 单测 + 集成测试；协议与设计文档更新

### 实现进度

| Phase | 状态 | 说明 |
|---|---|---|
| 设计确认 | ✅ | 用户确认 |
| 协议/房间 host | ✅（M3 已有） | host_player_id / start_battle 仅 host / battle_ready |
| Phase2 join+Web | ✅ 代码 | join_gate + webui + join_flow + bootstrap |
| Phase3 worker 权威 | ✅ 代码 | worker_pose 中继；原地 Bot；catalog_hash；worker 不进 Offline 单机 |
| Phase4 呈现/离开 | ✅ 代码 | RemoteScene；leave；Web 连接/选图/自动结束 |
| 房间完善 | ✅ 代码 | select_map；时限/无人自动结束；Web 选图 |
| 真机验收 | ⬜ | 需 launcher build/deploy 后双端联调 |
| Worker 先进局 | ✅ 代码 | worker_entered 后再拉玩家进同一回合；worker_pose 日志 5s 限流 |
| 完整 0.9.22 呈现 | 后置 | 私有 worker 空间 + 远端 Vehicle 绑定 |

## 11. 风险

1. **最早拦截点**：2.3.1.2 车库 UI 路径与 0.9.22 不同；需真机试钩子，防止 joining 层仍出现。
2. **0.9.22 呈现层移植**：#1513 与 2.3.1.2 Vehicle/CompoundAppearance API 差异大，需适配与降级。
3. **Worker 进 Offline battle 空间**：与可见客户端 Offline hangar 并存；需避免抢权威、避免 fake_server 单机路径干扰。
4. **Web 在客户端**：多开端口、浏览器拉起、与游戏线程安全；失败需有日志回退路径。
5. **车数据校验字段**：M6 可能只能做 compact descr / 子集哈希，完整 XML profile 后置。

## 12. 已确认决策摘要

| 议题 | 结论 |
|---|---|
| M5 真机 | 已到车库；join 会进单机 → M6 必须拦截 |
| 权威物理 | 独立游戏进程（worker），Offline battle 空间 |
| 拓扑 | 0.9.22 三层（客户端 → Python 服务器 → 游戏 worker） |
| 进入 | 尽早拦截；点战斗开浏览器 Web |
| 房间 UI | 不用游戏内 UI；本机 Web 状态页 |
| Web 宿主 | 玩家客户端本机 HTTP，非 sim-worker |
| Web 范围 | 状态 + 开战；仅房主开战 |
| 房主 | 首连 player |
| 地图/车 | 无白名单 |
| 车数据 | M6 一致性校验；profile 下发后置 |
| Bot | M6 原地；AI 后置 |
| 呈现 | 移植 0.9.22 呈现层 |
| 离开 | 回车库；结果屏后置 |
| 联机 | 局域网；固定主机手填 IP |
| Web 端口 | 18080 起自动递增 |
| Worker 进 battle | 仅 start_battle 之后 |
| 单机 | 同路径 server+worker+player+Web |
