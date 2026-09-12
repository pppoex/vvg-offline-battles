# HANDOFF.md

> 交接记录 — 给下一个 Agent 的最重要文件

## 当前阶段

**M4 完成并真机通过：进车库 + player/worker 均可 join sim-worker**

M0 多实例、M1 SDK、M2 协议、M3 服务器骨架、M4 薄客户端均已完成。  
下一步：**M5 命令行启动器与统一部署**。

远程仓库：https://github.com/pppoex/vvg-offline-battles  
分支：`main`（开发）、`base`（存档）

## 最后 commit

- **hash**: `09aac72`
- **message**: `feat(multiclient): worker starter 支持 --show/--hide 控制隐藏窗口 [TASK-M4]`
- **已推送**: `master` → `origin/main`

M4 关键业务 commit 摘要：

| commit | 说明 |
|---|---|
| `b89dbf9` | 薄客户端网络层与协议会话 |
| `cf92edb` | 防止 bootstrap 崩溃游戏 + 路径/junction 修复 |
| `88e8a5e` | install_offhangar 部署脚本 |
| `5f0e3a7` | 修复 Offline 入口 Decompyle UnboundLocalError |
| `6e08cd1` | sim-worker 接入/离开/开战日志 |
| `9c7a1d6` | simulation_worker 角色 + ready 标记 |
| `09aac72` | starter `--show`/`--hide` |

## 已完成

1. **TASK-000 ~ TASK-007**: 初始化与第一阶段只读分析
2. **TASK-M0 ~ M0.F**: 多实例限制解除（双开验证通过）
3. **TASK-M1**: 项目骨架与 SDK 抽取
4. **TASK-M2**: 协议与序列化
5. **TASK-M3**: sim-worker 权威服务器骨架
6. **TASK-M4**: 薄客户端补丁（**真机通过**）
   - `src/client/vvg_client/**` — network / prediction / session / hooks
   - `src/client/mod_vvg_client.py` — BigWorld 入口（init **永不抛异常**）
   - `src/client/offline_entry/mod_offhangar2.py` — 修复 Decompyle 入口
   - `src/deploy/install_client.py` / `install_offhangar.py`
   - sim-worker 接入/离开/开战日志；接受 `role=worker`
   - starter：`--player` / `--worker-only` / `--show` / `--hide`
   - 单测 + 集成测试全绿；Py2.7 可编译
   - **真机**：进车库；player `handshake ok` + `join`；worker `role=worker` 可连

## 未完成

1. **M5: 命令行启动器与部署**（下一个里程碑）
2. **M6-M9**: 后续里程碑
3. 运动积分 / 射击 / Bot / 重连接线（M6-M8）
4. **WGC cleanup thunk x64 RVA 逆向**（低优先级）
5. **install_atmosphere_owner_guard**（0.9.22 专属，不阻塞）

## 正在处理

- M4 已收尾；等待用户确认进入 **M5**

## 下一步建议（M5）

1. `src/launcher/` — 一条命令拉起 sim-worker + 可选 player/worker
2. 统一部署：`install_client` + `install_multiclient` + `install_offhangar`（或合一）
3. 设置 `VVG_PLAYER_NAME` / `VVG_PLAYER_VEHICLE` / `VVG_SERVER_*` / `VVG_CLIENT_MODE`
4. 避免残留旧 sim-worker 占 28782（真机联调时已踩坑）
5. `tests/integration/test_launcher.py`
6. 真机：launcher 一键 → 车库 + sim-worker join

## 关键文件

### M4

- `src/client/vvg_client/network/{client,connection,reconnect}.py`
- `src/client/vvg_client/{session,bootstrap}.py`
- `src/client/vvg_client/hooks/bigworld_hooks.py`
- `src/client/mod_vvg_client.py`
- `src/client/offline_entry/mod_offhangar2.py`
- `src/multiclient/native/worker_starter.c`
- `src/deploy/install_client.py` / `install_offhangar.py`
- `src/sim_worker/server.py`（日志 + worker 角色）
- `tests/integration/test_client.py`
- `docs/design/thin_client.md`

### M3 / M2 / M1 / M0

- `src/sim_worker/**` · `src/protocol/**` · `src/sdk/**` · `src/multiclient/**`
- `docs/design/sim_worker.md` · `protocol.md` · `thin_client.md`

### 源项目（只读）

- `D:\Projects\Offline2.3.1.2` — Offline mod 源（**勿写**）
- `D:\Projects\wot-offline-battles` — 0.9.22 参考（只读）
- `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2` — 游戏安装（部署脚本可写 res_mods）

## 关键发现（M4 真机）

1. **mod init 必须永不抛异常**，否则 `game.init` 整段失败退出。
2. 游戏路径可能经 **junction**：`__file__` 可能缺 `res_mods\2.3.1.2`；bootstrap 需扫 `res_mods/<ver>` 并用 `import protocol` 校验。
3. Offline 入口 Decompyle 产物 `offhangar2 = offhangar2` 会崩；部署用 `src/client/offline_entry/mod_offhangar2.py` 修复版。
4. **必须同时部署** Offline hangar（`install_offhangar`）才能进车库；仅 vvg 客户端会停在登录。
5. `BigWorld.callback` 正确；`addCallback` 不存在。
6. 服务器 skeleton 默认不打 join 日志；已补。旧 sim-worker 占 28782 时会“看起来没连上”。
7. `VVG_CLIENT_MODE=simulation_worker` → role=worker hello；握手后写 `VVG_WORKER_READY_MARKER`。
8. starter 默认隐藏 worker；`--worker-only --show` 可见调试。
9. 部署杂项：`mods` 下勿依赖 Py3 `__pycache__`；游戏只认 magic=62211 的 .pyc。

## 环境 / 联调速查

```powershell
# sim-worker
cd D:\Projects\vvg-offline-battles
$env:PYTHONPATH = "src"
python -m sim_worker.main --host 127.0.0.1 --port 28782 --map training

# player
cd "D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\win64"
.\vvg_worker_starter.exe --player

# 可见 worker
.\vvg_worker_starter.exe --worker-only --show

# 部署
python src/deploy/install_multiclient.py
python src/deploy/install_client.py
python src/deploy/install_offhangar.py

# 测试
python -m pytest tests/unit tests/integration -q
```

日志：游戏根 `vvg-player-python.log` / `vvg-worker-python.log` / `offhangar2.log`；sim-worker 控制台。

## 风险

1. Offline hangar 与 vvg 薄客户端并行加载，M6 战斗路径需避免 Offline battle 与 sim-worker 抢权威。
2. 真实 drive/shooting 迁入需拆 Offline 大文件。
3. 宿主无法加载 Py2.7 pyd — 游戏内验证以日志为准。
4. 多开时注意 worker 单例互斥 `Local\vvg_offline_worker`。

## 待用户确认

1. ~~M0-M4~~ — 已完成（M4 真机通过）
2. 是否继续 **M5（命令行启动器与统一部署）**
3. Bot AI 范围 / 单人模式：DECISIONS 已倾向「基础 Bot」「单人也启 sim-worker」，M6 前最终确认

## 禁止事项提醒

- 禁止修改 `D:\Projects\Offline2.3.1.2`
- 禁止修改 `D:\Projects\wot-offline-battles`
- 禁止修改游戏 exe/dll/核心 pkg（res_mods 经部署脚本写入）
- 禁止无证据编造 API/协议
- 禁止大文件堆逻辑；必须测试 + 文档
- 禁止客户端路径使用 Py3-only 语法
