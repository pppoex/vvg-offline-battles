# HANDOFF.md

> 交接记录 — 给下一个 Agent 的最重要文件

## 当前阶段

**M0–M5 完成；M6 Phase2–4 代码完成（待真机验收）**

- Phase2：join 拦截 + 本机 Web
- Phase3：worker_pose 中继、原地 Bot、catalog_hash、worker 尝试进 Offline battle
- Phase4：RemoteScene（插值远端 pose 注册表）、leave 回车库、Web `/leave`
- 完整 0.9.22 compound Vehicle 呈现 **未移植**（需 2.3.1.2 API 适配）
- 下一步：真机 build/deploy 联调；再考虑呈现深度

远程仓库：https://github.com/pppoex/vvg-offline-battles  
分支：`main`（开发，本地名 `master`）、`base`（存档）

## 最后 commit

- **hash**: `eeb68e7`
- **message**: `feat(sim_worker): worker pose 中继与原地 Bot [TASK-M6]`
- **已推送**: `master` → `origin/main`

M5 关键业务 commit：

| commit | 说明 |
|---|---|
| `8e4f0da` | 命令行启动器与统一部署 |
| `6ff7ad5` | 构建产物统一到 `build/` + `launcher build` |
| `f08dceb` | build 阶段编译 Python 2.7 pyc 至 `build/` |

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
7. **TASK-M5**: 命令行启动器与统一部署（**代码+测试完成；真机一键待验**）
   - `src/launcher/{cli,paths,env,ports,server,client,build,bytecode}.py`
   - `src/deploy/install_all.py` 薄壳串联
   - `tests/integration/test_launcher.py`
   - `docs/design/launcher.md`
   - 子命令：`build` / `deploy` / `server` / `player` / `worker`（独立，不捆绑一键全起）
   - 端口占用默认报错；`--kill-port` 才清理
   - **构建产物统一在 `build/`（镜像 `src/`）**：native + **Py2.7 .pyc（magic=62211）**；`src/` 仅源码；`out/` 与 `dist/` 已废弃
   - `python -m launcher build` = native + pyc 两组件

## 未完成

1. **M5 真机验证**：launcher 一键 → 车库 + sim-worker accept/join
2. **M6-M9**: 后续里程碑
3. 运动积分 / 射击 / Bot / 重连接线（M6-M8）
4. **WGC cleanup thunk x64 RVA 逆向**（低优先级）
5. **install_atmosphere_owner_guard**（0.9.22 专属，不阻塞）

## 正在处理

- M6 Phase2 代码完成；Phase3+ 未开始
- 真机：点战斗应打开浏览器状态页（需 launcher build+deploy）

## 下一步建议

### M6 Phase3（优先）

1. worker 收 start_battle 后进入 Offline battle 空间（安全降级）
2. 原地 Bot 名册；worker pose → snapshot 中继
3. 车数据一致性校验

### M6 Phase4

1. 远端车呈现（0.9.22 适配或最小 pose 驱动）
2. leave_battle 回车库细化
3. 真机双开 + 局域网

### 真机（Phase2）

```powershell
$env:PYTHONPATH = "src"
python -m launcher build
python -m launcher deploy
python -m launcher server
python -m launcher worker --hide
python -m launcher player --name Alice
# 车库点「战斗」→ 应打开 http://127.0.0.1:18080/
```

## 关键文件

### M5

- `src/launcher/**`（含 `build.py` / `bytecode.py`）
- `src/deploy/install_all.py` / `install_*.py`
- `src/multiclient/native/build.ps1`（输出到 `build/`）
- `tests/integration/test_launcher.py`
- `docs/design/launcher.md`

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

## 关键发现（M4 真机 + M5 构建）

1. **mod init 必须永不抛异常**，否则 `game.init` 整段失败退出。
2. 游戏路径可能经 **junction**：`__file__` 可能缺 `res_mods\2.3.1.2`；bootstrap 需扫 `res_mods/<ver>` 并用 `import protocol` 校验。
3. Offline 入口 Decompyle 产物 `offhangar2 = offhangar2` 会崩；部署用 `src/client/offline_entry/mod_offhangar2.py` 修复版。
4. **必须同时部署** Offline hangar（`install_offhangar`）才能进车库；仅 vvg 客户端会停在登录。
5. `BigWorld.callback` 正确；`addCallback` 不存在。
6. 服务器 skeleton 默认不打 join 日志；已补。旧 sim-worker 占 28782 时会“看起来没连上”。
7. `VVG_CLIENT_MODE=simulation_worker` → role=worker hello；握手后写 `VVG_WORKER_READY_MARKER`。
8. starter 默认隐藏 worker；`--worker-only --show` 可见调试。
9. 部署杂项：`mods` 下勿依赖 Py3 `__pycache__`；游戏只认 magic=62211 的 .pyc。
10. **`src/` 只放源码**；`.pyd`/`.exe`/`.obj`/`.pyc` 一律进 `build/`（镜像 `src/`）。历史 `native/out/` 与 `dist/` 已废弃。

## 环境 / 联调速查

```powershell
# 推荐（M5 launcher）
cd D:\Projects\vvg-offline-battles
$env:PYTHONPATH = "src"
python -m launcher build              # native + pyc → build/
python -m launcher deploy
python -m launcher server            # 可选 --kill-port
python -m launcher player --name Alice
python -m launcher worker --show     # 可选

# 旧路径（仍可用）
python -m sim_worker.main --host 127.0.0.1 --port 28782 --map training
cd "D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\win64"
.\vvg_worker_starter.exe --player

# 部署（仍可用）
python src/deploy/install_all.py
# 或分步
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
5. launcher `--force-game-exe` 不注入多开守卫，双开场景勿用。

## 待用户确认

1. ~~M0-M4~~ — 已完成
2. ~~M5 进车库~~ — 已确认可进车库；join 进单机由 M6 拦截处理
3. ~~M6 架构选项~~ — **已确认**（m6_architecture）
4. M6 编码开工后：真机验收 join 不卡、双端同步、局域网加入

## 禁止事项提醒

- 禁止修改 `D:\Projects\Offline2.3.1.2`
- 禁止修改 `D:\Projects\wot-offline-battles`
- 禁止修改游戏 exe/dll/核心 pkg（res_mods 经部署脚本写入）
- 禁止无证据编造 API/协议
- 禁止大文件堆逻辑；必须测试 + 文档
- 禁止客户端路径使用 Py3-only 语法
- 禁止把构建产物写回 `src/`
