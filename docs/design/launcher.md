# 命令行启动器设计（M5）

> Python 3 · 不在游戏内加载 · 默认端口 28782

## 1. 目标

提供统一的用户入口，替代「手敲三条 deploy + 手起 sim-worker + 手起 starter」的碎片流程：

- **deploy**：一键串联部署 multiclient / thin client / offhangar
- **server**：只启动权威 sim-worker
- **player**：只启动一个 player 游戏客户端
- **worker**：只启动一个 simulation_worker 客户端（可选显示/隐藏）

单人也走同一路径（DECISIONS：不保留单机模式；单人也连本地 sim-worker）。
server / player / worker **彼此独立**，由用户按需在多个终端打开。

## 2. 模块

| 路径 | 职责 |
|---|---|
| `src/launcher/cli.py` | argparse 子命令入口 |
| `src/launcher/paths.py` | 工作区根 / 游戏根 / starter 路径 |
| `src/launcher/env.py` | 组装 `VVG_*` 环境变量 |
| `src/launcher/ports.py` | 端口占用检测；可选 kill 本地监听 |
| `src/launcher/server.py` | 起停 sim-worker，等端口就绪 |
| `src/launcher/client.py` | 经 `vvg_worker_starter.exe` 拉起 player/worker |
| `src/deploy/install_all.py` | 串联三个 install 脚本（薄壳） |

入口：

```powershell
python -m launcher deploy
python -m launcher server
python -m launcher player
python -m launcher worker
```

（等价：`python src/launcher/cli.py …`；`pythonpath` 需含 `src`。）

## 3. 子命令

### 3.1 deploy

```
python -m launcher deploy [--game-root PATH] [--python27 PATH]
                          [--only multiclient|client|offhangar]
                          [--skip multiclient|client|offhangar]
                          [--skip-sdk] [--dry-run]
```

顺序执行（可被 only/skip 收窄）：

1. `install_multiclient` — 守卫 + starter
2. `install_client` — 薄客户端 + protocol/sdk vendor
3. `install_offhangar` — Offline 车库入口

任一组件失败 → 退出码 1。

### 3.2 server

```
python -m launcher server [--host H] [--port P] [--map NAME]
                          [--kill-port] [--ready-timeout N]
```

1. 默认**不**自动杀端口占用：若 `host:port` 已监听 → 打印 pids，退出码 2
2. `--kill-port`：先 `taskkill /T /F` 本地 LISTENING pid，再起服
3. 子进程 `python -m sim_worker.main`（`PYTHONPATH=工作区/src`）
4. 轮询至端口就绪；前台阻塞，Ctrl+C → terminate 子进程

### 3.3 player

```
python -m launcher player [--name N] [--vehicle V]
                          [--host H] [--port P]
                          [--game-root PATH] [--force-game-exe]
```

1. 优先 `win64\vvg_worker_starter.exe --player`
2. 缺失 starter 且未 `--force-game-exe` 时报错提示 deploy
3. `--force-game-exe`：直接 `WorldOfTanks.exe`（无多开守卫注入，仅调试）
4. 设置：

| 变量 | 值 |
|---|---|
| `VVG_CLIENT_MODE` | `player` |
| `VVG_PLAYER_NAME` | `--name` 或 `Player` |
| `VVG_PLAYER_VEHICLE` | `--vehicle` 或 `ussr:R05_LT` |
| `VVG_SERVER_HOST` / `PORT` | 默认 `127.0.0.1` / `28782` |
| `VVG_ALLOW_MULTIPLE_CLIENTS` | `1` |

拉起后 launcher 退出；游戏进程独立存活。

### 3.4 worker

```
python -m launcher worker [--show|--hide] [--host H] [--port P]
                          [--game-root PATH] [--force-game-exe]
```

- 默认交给 starter 自行决定隐藏桌面（与 M4 一致）
- `--show` → `--worker-only --show`（可见调试）
- `--hide` → `--worker-only --hide`
- `VVG_CLIENT_MODE=simulation_worker`

## 4. 环境变量一览

| 变量 | 写入方 | 读取方 |
|---|---|---|
| `VVG_SERVER_HOST` / `VVG_SERVER_PORT` | launcher server/player/worker | client bootstrap / 可选 sim-worker |
| `VVG_PLAYER_NAME` / `VVG_PLAYER_VEHICLE` | launcher player | client bootstrap |
| `VVG_CLIENT_MODE` | launcher player/worker；starter 也会写 | client bootstrap |
| `VVG_ALLOW_MULTIPLE_CLIENTS` | launcher client；starter 也会写 | instance_guard |
| `VVG_GAME_ROOT` | 用户可选 | launcher paths.game_root |
| `VVG_WORKER_READY_MARKER` | starter | client bootstrap（worker 握手后写标记） |

## 5. 典型联调流程

```powershell
# 0) 一次性部署
cd D:\Projects\vvg-offline-battles
python -m launcher deploy

# 1) 终端 A：权威服（残留旧进程时加 --kill-port）
python -m launcher server

# 2) 终端 B：player
python -m launcher player --name Alice

# 3) 终端 C（可选）：可见 worker 调试
python -m launcher worker --show
```

## 6. 测试

```powershell
python -m pytest tests/integration/test_launcher.py -q
python -m pytest tests/unit tests/integration -q
```

覆盖：env 组装、starter argv、端口占用拒绝、sim-worker 子进程 bind、CLI 解析、install_all 组件选择与 dry-run。

## 7. 刻意不做（边界）

- 不做「一键同时起 server+player」的捆绑（用户明确要求独立控制）
- 不自动 kill 端口（除非 `--kill-port`）
- 不在 launcher 内重写 deploy 逻辑（只薄壳调用 install_*）
- 不做 GUI；不修改游戏 exe/dll/pkg
