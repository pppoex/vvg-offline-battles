# -*- coding: utf-8 -*-
"""能力协商 — 客户端/服务器能力集合与交集校验。

对齐 0.9.22：能力名是短字符串列表，hello 声明、welcome 回显双方集合；
服务器检查客户端是否包含 required 子集。
"""
from __future__ import absolute_import, division, print_function

from protocol.constants import (
    MAX_CAPABILITY_COUNT,
    MAX_CAPABILITY_LENGTH,
)

# --- 能力名常量（语义沿用参考项目，值可按 2.3.1.2 调整） ------------------

# 基础会话（M2 必选）
CAP_CORE_SESSION_V1 = 'core_session_v1'

# 移动 / 快照（M6）
CAP_MOVEMENT_SYNC_V1 = 'movement_sync_v1'
CAP_LEAN_SNAPSHOT_V1 = 'lean_snapshot_v1'

# 射击 / 弹道（M7）
CAP_FIRE_INTENT_V1 = 'fire_intent_v1'
CAP_PROJECTILE_LEDGER_V1 = 'projectile_ledger_v1'

# Bot / 权威 worker
CAP_SIMULATION_WORKER_V1 = 'simulation_worker_v1'
CAP_BOT_STATE_V1 = 'bot_state_v1'

# 断线重连（M8）
CAP_RECONNECT_V1 = 'reconnect_v1'

# M2 客户端默认能力：核心会话即可建立连接
DEFAULT_CLIENT_CAPABILITIES = (
    CAP_CORE_SESSION_V1,
)

# M2 服务器默认能力
DEFAULT_SERVER_CAPABILITIES = (
    CAP_CORE_SESSION_V1,
    CAP_MOVEMENT_SYNC_V1,
    CAP_LEAN_SNAPSHOT_V1,
)

# M2 必选能力：双方都必须声明
REQUIRED_CAPABILITIES = (
    CAP_CORE_SESSION_V1,
)


class CapabilityError(ValueError):
    """能力列表不合法或不满足 required 子集。"""


def normalize_capabilities(value):
    """把任意输入规范为有序去重的能力列表。

    接受 list/tuple/frozenset/set；元素必须是非空短 str。
    返回 list[str]。非法输入抛 CapabilityError。
    """
    if value is None:
        return []
    if not isinstance(value, (list, tuple, frozenset, set)):
        raise CapabilityError('capabilities must be a sequence of strings')
    if len(value) > MAX_CAPABILITY_COUNT:
        raise CapabilityError('too many capabilities')

    seen = []
    seen_set = set()
    for item in value:
        if not isinstance(item, (str, bytes)):
            # Py2: basestring 里的 unicode
            try:
                text_types = (unicode,)  # noqa: F821
            except NameError:
                text_types = ()
            if not text_types or not isinstance(item, text_types):
                raise CapabilityError('capability must be a string')
        if isinstance(item, bytes):
            try:
                item = item.decode('ascii')
            except UnicodeDecodeError:
                raise CapabilityError('capability must be ascii text')
        if not item or len(item) > MAX_CAPABILITY_LENGTH:
            raise CapabilityError('invalid capability name length')
        if item in seen_set:
            continue
        seen_set.add(item)
        seen.append(item)
    return seen


def contains_required(capabilities, required=REQUIRED_CAPABILITIES):
    """返回 capabilities 是否包含全部 required。"""
    if required is None:
        return True
    present = set(normalize_capabilities(capabilities))
    for name in required:
        if name not in present:
            return False
    return True


def intersect(left, right):
    """返回双方能力交集（保持 left 顺序）。"""
    right_set = set(normalize_capabilities(right))
    return [name for name in normalize_capabilities(left) if name in right_set]


def negotiate(client_capabilities, server_capabilities,
              required=REQUIRED_CAPABILITIES):
    """协商结果。

    返回 dict:
      ok: bool
      client: list — 规范化后的客户端能力
      server: list — 规范化后的服务器能力
      shared: list — 交集
      missing: list — 客户端缺失的 required 能力
    """
    client = normalize_capabilities(client_capabilities)
    server = normalize_capabilities(server_capabilities)
    missing = [
        name for name in (required or ())
        if name not in set(client)
    ]
    ok = not missing and contains_required(server, required)
    return {
        'ok': ok,
        'client': client,
        'server': server,
        'shared': intersect(client, server),
        'missing': missing,
    }


def validate_capability_list(value):
    """校验并返回规范化列表；失败抛 CapabilityError。"""
    return normalize_capabilities(value)
