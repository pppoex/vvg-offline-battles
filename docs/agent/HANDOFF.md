# HANDOFF.md

> 交接记录 — 给下一个 Agent 的最重要文件

## 当前阶段

**M1 完成：项目骨架与 SDK 抽取，单测全绿**

M0 多实例限制解除（双开验证通过）与 M1 SDK 骨架均已完成。

远程仓库：https://github.com/pppoex/vvg-offline-battles

## 最后 commit

- **hash**: （见 git log 最新 TASK-M1）
- **message**: `feat(sdk): 抽取 hooks/log/config 并实现 math 库 [TASK-M1]`
- **已推送**: 待确认是否 push origin master:main

## 已完成

1. **TASK-000 ~ TASK-007**: 初始化与第一阶段只读分析
2. **TASK-M0 ~ M0.F**: 多实例限制解除（双开验证通过，已推 GitHub）
3. **TASK-M1**: 项目骨架与 SDK 抽取
   - `pyproject.toml` — setuptools + pytest（pythonpath=src）
   - `src/sdk/hooks.py` — override/setAttr，修 Decompyle artifact
   - `src/sdk/log.py` — 文件日志 + guard 装饰器
   - `src/sdk/config.py` — 去掉 OFFLINE_*；SERVER_HOST/PORT、重连策略等
   - `src/sdk/math/vector.py` — Vector3（dot/cross/normalise/lerp）
   - `src/sdk/math/matrix.py` — Matrix 4x4（yaw/pitch/roll、applyPoint/Vector）
   - `tests/unit/test_sdk_{hooks,log,config,vector,matrix}.py`
   - 顺带修复：Python 3.14 下 M0 测试不再依赖已移除的 `imp` 模块
   - 验证：`python -m pytest tests/unit -q` 全绿（1 skip）；SDK 在 D:\Python27 下可编译

## 未完成

1. **M2: 协议与序列化**（下一个里程碑）
2. **M3: sim-worker 权威服务器**
3. **M4: 薄客户端补丁**
4. **M5-M9**: 后续里程碑
5. **WGC cleanup thunk x64 RVA 逆向**（低优先级，句柄枚举方案已可用）
6. **install_atmosphere_owner_guard**（0.9.22 专属，不阻塞）

## 正在处理

- M1 刚完成；等待进入 M2

## 下一步建议

进入 **M2: 协议与序列化**：

1. 创建 `src/protocol/`：`constants.py` / `messages.py` / `serializer.py` / `capabilities.py`
2. 参考 0.9.22 的 JSON lines over TCP，PROTOCOL_VERSION=5
3. 默认端口与 `sdk/config.py` 的 `SERVER_PORT=28782` 对齐
4. 单元测试 `tests/unit/test_protocol.py`、`test_serializer.py`
5. 参考 `docs/analysis/05-migration-and-sdk-plan.md` §5.1 与 M2 里程碑说明

## 关键文件

### M1（本轮）

- `pyproject.toml`
- `src/sdk/hooks.py`
- `src/sdk/log.py`
- `src/sdk/config.py`
- `src/sdk/math/vector.py`
- `src/sdk/math/matrix.py`
- `tests/unit/test_sdk_*.py`

### M0

- `src/multiclient/native/instance_guard.c`
- `src/multiclient/native/worker_starter.c`
- `src/multiclient/instance_guard.py`
- `src/client/mod_vvg_instance_guard.py`
- `src/client/vvg_instance_guard/bootstrap.py`
- `src/deploy/install_multiclient.py`

### 分析文档

- `docs/analysis/05-migration-and-sdk-plan.md` — SDK 抽取计划
- `docs/analysis/multiclient-research.md` — M0 逆向报告
- `docs/agent/MILESTONES.md` — 里程碑总览

### 源项目（只读）

- `D:\Projects\Offline2.3.1.2`
- `D:\Projects\wot-offline-battles`
- `D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2`

## 关键发现

### SDK 抽取

- Offline 的 `hooks.py` / `log.py` 有 Decompyle++ artifact（`print text`、空 except 体），已在 SDK 中重写
- `config.py` 882 行里绝大多数是单机战斗参数，**不要整文件复制**；联机只需要网络/会话默认值 + JSON override 机制
- BigWorld `Math.Vector3` / `Math.Matrix` 用法：构造支持序列拷贝；`.translation`、`.yaw/.pitch/.roll`、`applyPoint`/`applyVector`
- 欧拉角：`setYawPitchRoll` 实现 R = Ry·Rx·Rz；pitch 向上抬为负

### 运行时

- 宿主 Python 3.14：`imp` 模块已移除，测试 helper 改用 `importlib.util`
- 游戏内嵌 Python 2.7：无 `_ctypes`，native 必须 `imp.load_dynamic`（M0 结论不变）
- SDK 须保持 2/3 兼容：禁 f-string、禁类型注解（运行时）

### M0 遗留结论（仍有效）

- 主互斥体：`WOT_STARTUP_MUTEX`
- 客户端只加载 `.pyc`，magic=62211
- 日志：`vvg-*-python.log`

## 风险

1. 协议设计若与 0.9.22 差异过大，M3/M4 适配成本高 — M2 时优先复用消息语义
2. sim-worker 迁移 Offline 大文件（drive/shooting 等）时仍需去 BigWorld 依赖
3. 宿主无法加载 Py2.7 pyd 作扩展 — 真机游戏内验证仍以游戏日志为准

## 待用户确认

1. ~~M0 真机双开~~ — 已通过
2. ~~继续 M1~~ — 已完成
3. 是否继续 **M2（协议与序列化）**

## 禁止事项提醒

- 禁止修改 `D:\Projects\Offline2.3.1.2`
- 禁止修改 `D:\Projects\wot-offline-battles`
- 禁止修改游戏安装目录、exe、dll、核心资源
- 禁止无证据编造 API、文件、协议
- 禁止把大量代码写进单文件
- 禁止跳过测试和文档
