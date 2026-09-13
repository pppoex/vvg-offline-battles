# OPEN_QUESTIONS.md

> 开放问题 — 需要用户确认或后续验证的问题

## 已解决的问题

### ~~问题：多实例方案选择~~ ✅ 已解决

- **结论**：采用 native C x64 + 句柄枚举释放（方案 1 变体）
- **实际实现**：
  - 逆向确认主互斥体是 `WOT_STARTUP_MUTEX`（非 0.9.22 的 `wot_client_mutex`）
  - 未定位 WGC cleanup thunk RVA，改用 `NtQuerySystemInformation` 句柄枚举
  - 通过 `imp.load_dynamic` 导入 pyd（游戏内嵌 Python 无 `_ctypes`）
- **验证**：用户确认双开正常
- **commit**: `78a989a`

### ~~问题：客户端部署方式~~ ✅ 已解决

- **结论**：res_mods 散装脚本 + .pyc 编译
- **实际实现**：
  - mod 放在 `res_mods/2.3.1.2/scripts/client/gui/mods/`
  - native pyd 放在 `mods/2.3.1.2/` 和 `win64/`
  - 部署脚本用 Python 2.7 编译 .pyc（magic=62211）
- **验证**：mod 成功加载并释放互斥体

---

## 待验证的问题（不阻塞）

### 问题：WGC cleanup thunk x64 RVA

- **为什么需要验证**：当前用句柄枚举替代，理论上不如调用引擎 cleanup 安全
- **验证方法**：
  1. IDA/Ghidra 交叉引用 `WGCControllerImpl` 析构与 `AppMutexWin32`
  2. 长时间多开压力测试
- **当前假设**：句柄枚举方案已验证可用，风险较低
- **是否阻塞**：否（M0 已通过验证）
- **优先级**：低（仅在出现稳定性问题时需要）

### 问题：install_atmosphere_owner_guard

- **为什么需要验证**：0.9.22 专属修复，2.3.1.2 返回状态 22（未映射）
- **影响**：不影响双开，可能影响某些 hangar 环境问题
- **是否阻塞**：否
- **优先级**：低（仅在出现特定问题时需要）

### ~~问题：2.3.1.2 Python .pyc magic number~~ ✅ 已解决

- **已确认**：magic = 62211 = `03 f3 0d 0a`（Python 2.7）
- **验证方法**：已通过实际编译和部署验证
- **状态**：✅ 已解决

### ~~问题：SDK Python 2/3 兼容~~ ✅ 已解决（M1）

- **结论**：`src/sdk/**` 保持 2/3 双兼容（禁 f-string / 运行时类型注解）
- **验证**：Py2.7 `py_compile` 全通过；Py3.14 pytest 全绿
- **状态**：✅ 已解决

### ~~问题：协议实现路径~~ ✅ 已解决（M2）

- **结论**：对齐 0.9.22 JSON lines v5；包路径 `src/protocol`；必选能力 `core_session_v1`
- **验证**：`pytest tests/unit/test_protocol.py tests/unit/test_serializer.py` 全绿；Py2.7 可编译
- **文档**：`docs/design/protocol.md`
- **状态**：✅ 已解决

### ~~问题：Offline config.py 整文件迁移~~ ✅ 已解决（M1）

- **结论**：不整文件复制；只保留 JSON override + 联机网络默认值
- **理由**：Offline 882 行多为单机 BATTLE_*/OFFLINE_* 开关
- **状态**：✅ 已解决

### 问题：openwg mod 功能

- **为什么需要验证**：不知道 openwg mod 的功能，可能冲突
- **验证方法**：
  1. 分析 openwg_*.pyd 的导出函数
  2. 测试共存（当前未发现冲突）
- **当前假设**：可能是网络/音频/字体相关的 mod，不影响我们的实例守卫
- **是否阻塞**：否
- **优先级**：低

---

## 待用户确认的问题

> **M6 架构已确认（2026-09）**：详见 `docs/design/m6_architecture.md` 与 DECISIONS。下列原开放项已关闭。

### ~~问题：Bot AI 范围~~ ✅ 已解决（M6）

- **结论**：M6 **原地 Bot**（出生后不动）；移动/射击 AI 推后
- **是否阻塞**：否

### ~~问题：单人模式处理~~ ✅ 已解决

- **结论**：单人同路径 server + worker + player + Web
- **是否阻塞**：否

### ~~问题：战斗模式范围~~ ✅ 已解决（M6）

- **结论**：自定义房语义；地图/车辆无白名单；权威在隐藏 worker
- **是否阻塞**：否

### ~~问题：地图支持范围~~ ✅ 已解决（M6）

- **结论**：无白名单，吃 Offline ArenaType 现有数据；资源不下发，校验同版本
- **是否阻塞**：否

### M6 已确认的新设计项（摘要）

| 项 | 结论 |
|---|---|
| 权威拓扑 | 0.9.22 三层 |
| Join 拦截 | 尽早；点战斗开浏览器 |
| 房间 UI | 本机 Web 状态页（非 sim-worker、非游戏内 UI） |
| 房主 | 首连 player；仅房主开战 |
| 联机 | 局域网；固定主机手填 IP |
| 车数据 | M6 一致性校验；profile 下发后置 |
| 远端呈现 | 移植 0.9.22 |
| Worker 进 battle | start_battle 之后 |
| Web 端口 | 18080 起自动递增 |

---

## 技术债务

| 债务 | 描述 | 优先级 |
|---|---|---|
| Offline2.3.1.2 Decompyle++ artifact | hooks.py 和 log.py 有反编译伪代码 | 低 |
| 大型模块拆分 | Offline2.3.1.2 的 drive/shooting 等需拆到 sim_worker/battle | 中（M6 时处理） |
| 测试覆盖率 | 需要完善测试覆盖 | 中（M9 时处理） |
| 文档完整性 | 需要完善文档 | 中（M9 时处理） |
