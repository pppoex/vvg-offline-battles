# -*- coding: utf-8 -*-
"""协议常量 — 消息类型、限制、默认地址。

对齐 0.9.22 参考项目：PROTOCOL_VERSION=5、JSON lines、端口 28782。
"""
from __future__ import absolute_import, division, print_function

# --- 版本 / 标识 -----------------------------------------------------------

PROTOCOL_VERSION = 5

# 2.3.1.2 客户端构建标签（占位；M4 接入时再绑定真实 build 字符串）
CLIENT_BUILD = 'wot-2.3.1.2-vvg'

ROLE_PLAYER = 'player'
ROLE_WORKER = 'worker'
KNOWN_ROLES = frozenset((ROLE_PLAYER, ROLE_WORKER))

# --- 传输 -----------------------------------------------------------------

# 单条消息上限（UTF-8 字节，不含换行）
MAX_MESSAGE_BYTES = 256 * 1024
# 接收缓冲上限（半行粘包余量）
MAX_BUFFER_BYTES = MAX_MESSAGE_BYTES * 2

JSONLINES_DELIMITER = b'\n'
JSONLINES_DELIMITER_TEXT = u'\n'

# 默认地址与 sdk.config.SERVER_* 对齐
DEFAULT_SERVER_HOST = '127.0.0.1'
DEFAULT_SERVER_PORT = 28782

# ping 间隔（秒），参考 lan_client.PING_INTERVAL
PING_INTERVAL = 1.0

# --- 能力协商限制 ----------------------------------------------------------

MAX_CAPABILITY_COUNT = 32
MAX_CAPABILITY_LENGTH = 64

# --- 消息类型 -------------------------------------------------------------

# 客户端 → 服务器
MSG_HELLO = 'hello'
MSG_LEAVE = 'leave'
MSG_LEAVE_BATTLE = 'leave_battle'
MSG_START_BATTLE = 'start_battle'
MSG_SELECT_VEHICLE = 'select_vehicle'
MSG_SELECT_TEAM = 'select_team'
MSG_BATTLE_READY = 'battle_ready'
MSG_INPUT = 'input'
MSG_PING = 'ping'

# 服务器 → 客户端
MSG_WELCOME = 'welcome'
MSG_ROSTER = 'roster'
MSG_BATTLE_START = 'battle_start'
MSG_BATTLE_LIVE = 'battle_live'
MSG_SNAPSHOT = 'snapshot'
MSG_EVENTS = 'events'
MSG_ERROR = 'error'
MSG_PONG = 'pong'

# 拒绝类（大厅配置）
MSG_START_DENIED = 'start_denied'
MSG_TEAM_DENIED = 'team_denied'

CLIENT_TO_SERVER_TYPES = frozenset((
    MSG_HELLO,
    MSG_LEAVE,
    MSG_LEAVE_BATTLE,
    MSG_START_BATTLE,
    MSG_SELECT_VEHICLE,
    MSG_SELECT_TEAM,
    MSG_BATTLE_READY,
    MSG_INPUT,
    MSG_PING,
))

SERVER_TO_CLIENT_TYPES = frozenset((
    MSG_WELCOME,
    MSG_ROSTER,
    MSG_BATTLE_START,
    MSG_BATTLE_LIVE,
    MSG_SNAPSHOT,
    MSG_EVENTS,
    MSG_ERROR,
    MSG_PONG,
    MSG_START_DENIED,
    MSG_TEAM_DENIED,
))

ALL_KNOWN_TYPES = CLIENT_TO_SERVER_TYPES | SERVER_TO_CLIENT_TYPES

# 状态屏障：到达后客户端应立即消费，不可被 snapshot 跳过
STATE_BARRIER_TYPES = frozenset((
    MSG_WELCOME,
    MSG_ROSTER,
    MSG_BATTLE_START,
    MSG_BATTLE_LIVE,
    MSG_START_DENIED,
    MSG_TEAM_DENIED,
    MSG_EVENTS,
    MSG_ERROR,
))

# 有序可靠消息（不可丢弃）
ORDERED_RECEIVE_TYPES = STATE_BARRIER_TYPES | frozenset((
    MSG_PONG,
))

# 需要携带 protocol 字段的服务器状态消息
SERVER_STATE_TYPES = frozenset((
    MSG_WELCOME,
    MSG_ROSTER,
    MSG_BATTLE_START,
    MSG_BATTLE_LIVE,
    MSG_START_DENIED,
    MSG_TEAM_DENIED,
    MSG_SNAPSHOT,
    MSG_EVENTS,
    MSG_ERROR,
))

# --- 常见错误 code ---------------------------------------------------------

ERROR_PROTOCOL_MISMATCH = 'protocol'
ERROR_UNSUPPORTED_ROLE = 'unsupported_role'
ERROR_UNSUPPORTED_CAPABILITIES = 'unsupported_capabilities'
ERROR_INVALID_HELLO = 'invalid_hello'
ERROR_JOIN_REJECTED = 'join_rejected'

# --- 大厅 / 战斗相位 -------------------------------------------------------

PHASE_WAITING = 'waiting'
PHASE_LOADING = 'loading'
PHASE_BATTLE = 'battle'
PHASE_FINISHED = 'finished'
PHASES = frozenset((
    PHASE_WAITING,
    PHASE_LOADING,
    PHASE_BATTLE,
    PHASE_FINISHED,
))

# --- 数值边界（输入信封，对齐参考项目宽松上界） ---------------------------

MAX_INPUT_SPEED = 200.0
MAX_GUN_PITCH = 1.2
MAX_ATTITUDE = 0.61
WORLD_BOUNDS = (2000.0, 1000.0, 2000.0)
MAX_ROUND_SECONDS = 14400
MIN_ROUND_SECONDS = 60
MAX_TEAM_SIZE = 15
MAX_TEXT_LENGTH = 64
