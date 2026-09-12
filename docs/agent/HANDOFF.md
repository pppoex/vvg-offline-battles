# HANDOFF.md

> 交接记录 — 给下一个 Agent 的最重要文件

## 当前阶段

**M4 完成：薄客户端补丁骨架，unit+integration 全绿**

M0 多实例、M1 SDK、M2 协议、M3 服务器骨架、M4 薄客户端均已完成。

远程仓库：https://github.com/pppoex/vvg-offline-battles

## 最后 commit

- **hash**: `b89dbf9`
- **message**: `feat(client): 实现薄客户端网络层与协议会话 [TASK-M4]`
- **已推送**: `master` → `origin/main`

## 已完成

1. **TASK-000 ~ TASK-007**: 初始化与第一阶段只读分析
2. **TASK-M0 ~ M0.F**: 多实例限制解除（双开验证通过）
3. **TASK-M1**: 项目骨架与 SDK 抽取
4. **TASK-M2**: 协议与序列化
5. **TASK-M3**: sim-worker 权威服务器骨架
6. **TASK-M4**: 薄客户端补丁（骨架）
   - `src/client/mod_vvg_client.py` — BigWorld 入口
   - `src/client/vvg_client/network/` — TcpLineConnection / BattleClient / ReconnectPolicy
   - `src/client/vvg_client/prediction/` — LocalPlayer / SnapshotBuffer 占位
   - `src/client/vvg_client/session.py` / `bootstrap.py` / `hooks/`
   - `src/deploy/install_client.py` — res_mods 部署 + .pyc
   - `tests/unit/test_client_network.py` + `tests/integration/test_client.py`
   - `docs/design/thin_client.md`
   - 验证：`python -m pytest tests/unit tests/integration -q` 全绿；Py2.7 py_compile 全过

## 未完成

1. **M5: 命令行启动器与部署**（下一个里程碑）
2. **M6-M9**: 后续里程碑
3. 运动积分 / 射击 / Bot / 重连接线（M6-M8）
4. **WGC cleanup thunk x64 RVA 逆向**（低优先级）
5. **install_atmosphere_owner_guard**（0.9.22 专属，不阻塞）

## 正在处理

- M4 刚完成；等待进入 M5（启动器）

## 下一步建议

进入 **M5: 命令行启动器与部署**：

1. `src/launcher/` — 解析参数、拉起 sim-worker、拉起客户端
2. 单人也启 sim-worker（DECISIONS 已定）
3. 设置 `VVG_PLAYER_NAME` / `VVG_PLAYER_VEHICLE` / `VVG_SERVER_*`
4. 统一部署脚本（instance_guard + thin client + protocol + sdk）
5. 集成测试 `tests/integration/test_launcher.py`
6. 真机：先 `install_client.py` + `install_multiclient.py`，再双开观察 `vvg-*.log`

## 关键文件

### M4（本轮）

- `src/client/vvg_client/network/client.py`
- `src/client/vvg_client/network/connection.py`
- `src/client/vvg_client/session.py`
- `src/client/vvg_client/bootstrap.py`
- `src/client/mod_vvg_client.py`
- `src/deploy/install_client.py`
- `tests/integration/test_client.py`
- `docs/design/thin_client.md`

### M3

- `src/sim_worker/**`
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
- `src/deploy/install_multiclient.py`

### 分析 / 设计文档

- `docs/design/protocol.md`
- `docs/design/sim_worker.md`
- `docs/design/thin_client.md`
- `docs/analysis/05-migration-and-sdk-plan.md`
- `docs/agent/MILESTONES.md`

### 源项目（只读）

- `D:\Projects\Offline2.3.1.2`
- `D:\Projects\wot-offline-battles`
- `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2`

## 关键发现

### M4 薄客户端

- 协议层完全复用 `protocol.messages` builder；客户端不另起 envelope
- 接收线程解码后入队；主线程 `pump`/`tick` 消费；有界队列优先丢旧 snapshot
- 部署时 vendored `protocol/` + `sdk/` 到 `gui/mods/`，bootstrap 把 mods 目录加入 `sys.path`
- 预测为常系数占位；权威快照行硬校正且该帧不再 step
- 身份可用环境变量 `VVG_PLAYER_NAME` / `VVG_PLAYER_VEHICLE` / `VVG_SERVER_HOST` / `VVG_SERVER_PORT`

### 协议 / SDK / 服务器（仍有效）

- PROTOCOL_VERSION=5；端口 28782；必选能力 `core_session_v1`
- 客户端 Python 2.7；服务器 Python 3；protocol/sdk 双兼容
- 主互斥体 `WOT_STARTUP_MUTEX`；.pyc magic=62211

## 风险

1. 真机 BigWorld hook（`addCallback`）尚未在游戏内验证——M5/M6 用日志确认
2. 真实战斗逻辑（drive/shooting）迁入时需拆分 Offline 大文件
3. 宿主无法加载 Py2.7 pyd — 游戏内验证以日志为准

## 待用户确认

1. ~~M0 真机双开~~ — 已通过
2. ~~M1 / M2 / M3 / M4~~ — 骨架完成
3. 是否继续 **M5（命令行启动器与部署）**
4. Bot AI 范围 / 单人模式：DECISIONS 已倾向「基础 Bot」「单人也启 sim-worker」，M6 前最终确认即可

## 禁止事项提醒

- 禁止修改 `D:\Projects\Offline2.3.1.2`
- 禁止修改 `D:\Projects\wot-offline-battles`
- 禁止修改游戏安装目录、exe、dll、核心资源
- 禁止无证据编造 API、文件、协议
- 禁止把大量代码写进单文件
- 禁止跳过测试和文档
