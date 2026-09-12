# -*- coding: utf-8 -*-
"""消息构造与基础校验。

所有 builder 返回普通 dict，字段名与 0.9.22 参考语义对齐；
不做网络 IO。校验函数失败时抛 ValueError / ProtocolError。
"""
from __future__ import absolute_import, division, print_function

from protocol import constants as C
from protocol.capabilities import normalize_capabilities


class ProtocolError(ValueError):
    """消息结构不合法。"""


# --- 基础工具 ---------------------------------------------------------------


def _require_type(message):
    if not isinstance(message, dict):
        raise ProtocolError('message must be a dict')
    kind = message.get('type')
    if not isinstance(kind, (str, bytes)) or not kind:
        raise ProtocolError('message.type is required')
    if isinstance(kind, bytes):
        kind = kind.decode('ascii')
        message['type'] = kind
    if kind not in C.ALL_KNOWN_TYPES:
        raise ProtocolError('unknown message type: %s' % kind)
    return kind


def _exact_int(value, name, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, int):
        # Py2 long
        try:
            long_type = long  # noqa: F821
        except NameError:
            long_type = ()
        if not long_type or not isinstance(value, long_type):
            raise ProtocolError('%s must be an int' % name)
    if low is not None and value < low:
        raise ProtocolError('%s below minimum' % name)
    if high is not None and value > high:
        raise ProtocolError('%s above maximum' % name)
    return int(value)


def _finite_float(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolError('%s must be a number' % name)
    result = float(value)
    if result != result or result in (float('inf'), float('-inf')):
        raise ProtocolError('%s must be finite' % name)
    return result


def _optional_text(value, name, max_len=C.MAX_TEXT_LENGTH):
    if value is None:
        return None
    if not isinstance(value, (str, bytes)):
        try:
            text_types = (unicode,)  # noqa: F821
        except NameError:
            text_types = ()
        if not text_types or not isinstance(value, text_types):
            raise ProtocolError('%s must be text' % name)
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    if len(value) > max_len:
        raise ProtocolError('%s too long' % name)
    return value


def _vector3(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ProtocolError('%s must be a 3-vector' % name)
    return (
        _finite_float(value[0], name + '[0]'),
        _finite_float(value[1], name + '[1]'),
        _finite_float(value[2], name + '[2]'),
    )


def _clamp_unit(value):
    result = _finite_float(value, 'unit')
    if result < -1.0:
        return -1.0
    if result > 1.0:
        return 1.0
    return result


def _base(kind, protocol=None):
    if protocol is None:
        protocol = C.PROTOCOL_VERSION
    return {
        'type': kind,
        'protocol': _exact_int(protocol, 'protocol', low=1),
    }


# --- 客户端 → 服务器 -------------------------------------------------------


def build_hello(name, vehicle, capabilities=None, client_build=None,
                role=C.ROLE_PLAYER, account_key=None, max_health=None,
                requested_team=None, extras=None):
    """客户端首条消息。必须是连接后的第一条线上消息。"""
    from protocol.capabilities import DEFAULT_CLIENT_CAPABILITIES

    if role not in C.KNOWN_ROLES:
        raise ProtocolError('invalid role: %s' % role)
    if capabilities is None:
        caps = normalize_capabilities(DEFAULT_CLIENT_CAPABILITIES)
    else:
        caps = normalize_capabilities(capabilities)

    message = _base(C.MSG_HELLO)
    message['client_build'] = _optional_text(
        client_build or C.CLIENT_BUILD, 'client_build', 64)
    message['capabilities'] = caps
    message['role'] = role

    if role == C.ROLE_PLAYER:
        message['name'] = _optional_text(name, 'name', 32)
        if not message['name']:
            raise ProtocolError('player hello requires name')
        message['vehicle'] = _optional_text(vehicle, 'vehicle', 96)
        if not message['vehicle']:
            raise ProtocolError('player hello requires vehicle')
        if account_key is not None:
            message['account_key'] = _optional_text(
                account_key, 'account_key', 64)
        if max_health is not None:
            message['max_health'] = _exact_int(
                max_health, 'max_health', low=1, high=10 ** 7)
        if requested_team in (1, 2):
            message['requested_team'] = int(requested_team)
        elif requested_team is not None:
            raise ProtocolError('requested_team must be 1 or 2')
    else:
        # worker 不携带假玩家身份
        if name:
            message['name'] = _optional_text(name, 'name', 32)

    if extras:
        if not isinstance(extras, dict):
            raise ProtocolError('extras must be a dict')
        for key, value in extras.items():
            if key not in message:
                message[key] = value
    return message


def build_leave():
    """关闭连接前的礼貌离开（不解散战斗语义）。"""
    return _base(C.MSG_LEAVE)


def build_leave_battle(round_id):
    """退出当前回合，TCP 保持连接。"""
    return {
        'type': C.MSG_LEAVE_BATTLE,
        'round_id': _exact_int(round_id, 'round_id', low=0),
    }


def build_start_battle(round_id=0, requested_round_seconds=None):
    """host 请求开始战斗。"""
    message = {
        'type': C.MSG_START_BATTLE,
        'round_id': _exact_int(round_id, 'round_id', low=0),
    }
    if requested_round_seconds is not None:
        message['round_seconds'] = _exact_int(
            requested_round_seconds, 'round_seconds',
            low=C.MIN_ROUND_SECONDS, high=C.MAX_ROUND_SECONDS)
    return message


def build_select_vehicle(vehicle, vehicle_compact_descr=None,
                         max_health=None):
    message = {
        'type': C.MSG_SELECT_VEHICLE,
        'vehicle': _optional_text(vehicle, 'vehicle', 96),
    }
    if not message['vehicle']:
        raise ProtocolError('select_vehicle requires vehicle')
    if vehicle_compact_descr is not None:
        message['vehicle_compact_descr'] = _optional_text(
            vehicle_compact_descr, 'vehicle_compact_descr', 64 * 1024)
    if max_health is not None:
        message['max_health'] = _exact_int(
            max_health, 'max_health', low=1, high=10 ** 7)
    return message


def build_select_team(team):
    """team: 0=auto, 1, 2。"""
    team = _exact_int(team, 'team', low=0, high=2)
    return {
        'type': C.MSG_SELECT_TEAM,
        'team': team,
    }


def build_battle_ready(round_id):
    """客户端资源加载完成，进入倒计时。"""
    return {
        'type': C.MSG_BATTLE_READY,
        'round_id': _exact_int(round_id, 'round_id', low=0),
    }


def build_input(round_id, forward, turn, aim_yaw=0.0, gun_pitch=0.0,
                input_seq=0, position=None, yaw=None, fire_seq=0,
                pitch=None, roll=None, speed=None):
    """玩家输入信封。字段对齐参考项目 input 消息的核心子集。"""
    message = {
        'type': C.MSG_INPUT,
        'round_id': _exact_int(round_id, 'round_id', low=0),
        'input_seq': _exact_int(input_seq, 'input_seq', low=0),
        'forward': _clamp_unit(forward),
        'turn': _clamp_unit(turn),
        'aim_yaw': _finite_float(aim_yaw, 'aim_yaw'),
        'gun_pitch': _finite_float(gun_pitch, 'gun_pitch'),
        'fire_seq': _exact_int(fire_seq, 'fire_seq', low=0),
    }
    if abs(message['gun_pitch']) > C.MAX_GUN_PITCH:
        raise ProtocolError('gun_pitch out of range')
    if position is not None:
        message['position'] = list(_vector3(position, 'position'))
        for index, bound in enumerate(C.WORLD_BOUNDS):
            if abs(message['position'][index]) > bound:
                raise ProtocolError('position out of world bounds')
    if yaw is not None:
        message['yaw'] = _finite_float(yaw, 'yaw')
    if pitch is not None:
        message['pitch'] = _finite_float(pitch, 'pitch')
        if abs(message['pitch']) > C.MAX_ATTITUDE:
            raise ProtocolError('pitch out of range')
    if roll is not None:
        message['roll'] = _finite_float(roll, 'roll')
        if abs(message['roll']) > C.MAX_ATTITUDE:
            raise ProtocolError('roll out of range')
    if speed is not None:
        message['speed'] = _finite_float(speed, 'speed')
        if abs(message['speed']) > C.MAX_INPUT_SPEED:
            raise ProtocolError('speed out of range')
    return message


def build_ping(seq, client_time):
    return {
        'type': C.MSG_PING,
        'seq': _exact_int(seq, 'seq', low=0),
        'client_time': _finite_float(client_time, 'client_time'),
    }


# --- 服务器 → 客户端 -------------------------------------------------------


def build_welcome(player_id, name, vehicle, team, map_name, phase,
                  round_id=0, state_revision=0, host_player_id=None,
                  capabilities=None, server_capabilities=None,
                  client_build=None, server_time_ms=None, spawn=None,
                  extras=None):
    """接受 hello 后的欢迎消息。"""
    from protocol.capabilities import DEFAULT_SERVER_CAPABILITIES

    message = _base(C.MSG_WELCOME)
    message['player_id'] = _exact_int(player_id, 'player_id', low=1)
    message['name'] = _optional_text(name, 'name', 32)
    message['vehicle'] = _optional_text(vehicle, 'vehicle', 96)
    message['team'] = _exact_int(team, 'team', low=1, high=2)
    message['map'] = _optional_text(map_name, 'map', 96)
    message['phase'] = _require_phase(phase)
    message['round_id'] = _exact_int(round_id, 'round_id', low=0)
    message['state_revision'] = _exact_int(
        state_revision, 'state_revision', low=0)
    if host_player_id is not None:
        message['host_player_id'] = _exact_int(
            host_player_id, 'host_player_id', low=0)
    message['capabilities'] = normalize_capabilities(
        capabilities if capabilities is not None else ())
    message['server_capabilities'] = normalize_capabilities(
        server_capabilities if server_capabilities is not None
        else DEFAULT_SERVER_CAPABILITIES)
    if client_build is not None:
        message['client_build'] = _optional_text(
            client_build, 'client_build', 64)
    if server_time_ms is not None:
        message['server_time_ms'] = _exact_int(
            server_time_ms, 'server_time_ms', low=0)
    if spawn is not None:
        message['spawn'] = {
            'x': _finite_float(spawn.get('x', 0.0), 'spawn.x'),
            'y': _finite_float(spawn.get('y', 0.0), 'spawn.y'),
            'z': _finite_float(spawn.get('z', 0.0), 'spawn.z'),
            'yaw': _finite_float(spawn.get('yaw', 0.0), 'spawn.yaw'),
        }
    if extras:
        if not isinstance(extras, dict):
            raise ProtocolError('extras must be a dict')
        for key, value in extras.items():
            if key not in message:
                message[key] = value
    return message


def build_roster(phase, round_id, state_revision, map_name, players,
                 host_player_id=None, team_size=None, extras=None):
    """大厅 / 战斗成员名单快照。"""
    if not isinstance(players, (list, tuple)):
        raise ProtocolError('players must be a list')
    message = _base(C.MSG_ROSTER)
    message['phase'] = _require_phase(phase)
    message['round_id'] = _exact_int(round_id, 'round_id', low=0)
    message['state_revision'] = _exact_int(
        state_revision, 'state_revision', low=0)
    message['map'] = _optional_text(map_name, 'map', 96)
    message['players'] = list(players)
    if host_player_id is not None:
        message['host_player_id'] = _exact_int(
            host_player_id, 'host_player_id', low=0)
    if team_size is not None:
        message['team_size'] = _exact_int(
            team_size, 'team_size', low=1, high=C.MAX_TEAM_SIZE)
    if extras:
        if not isinstance(extras, dict):
            raise ProtocolError('extras must be a dict')
        for key, value in extras.items():
            if key not in message:
                message[key] = value
    return message


def build_battle_start(round_id, map_name, state_revision=0, extras=None):
    message = _base(C.MSG_BATTLE_START)
    message['round_id'] = _exact_int(round_id, 'round_id', low=0)
    message['map'] = _optional_text(map_name, 'map', 96)
    message['state_revision'] = _exact_int(
        state_revision, 'state_revision', low=0)
    if extras:
        if not isinstance(extras, dict):
            raise ProtocolError('extras must be a dict')
        for key, value in extras.items():
            if key not in message:
                message[key] = value
    return message


def build_battle_live(round_id, server_tick, state_revision=0,
                      server_time_ms=None, countdown_seconds=None,
                      battle_duration_seconds=None, timing=None):
    """进入 loading/prebattle 屏障。"""
    message = _base(C.MSG_BATTLE_LIVE)
    message['round_id'] = _exact_int(round_id, 'round_id', low=0)
    message['server_tick'] = _exact_int(
        server_tick, 'server_tick', low=0)
    message['state_revision'] = _exact_int(
        state_revision, 'state_revision', low=0)
    if server_time_ms is not None:
        message['server_time_ms'] = _exact_int(
            server_time_ms, 'server_time_ms', low=0)
    if countdown_seconds is not None:
        message['countdown_seconds'] = _finite_float(
            countdown_seconds, 'countdown_seconds')
    if battle_duration_seconds is not None:
        message['battle_duration_seconds'] = _finite_float(
            battle_duration_seconds, 'battle_duration_seconds')
    if timing is not None:
        message['timing'] = dict(timing)
    return message


def build_snapshot(round_id, server_tick, server_time_ms, payload=None,
                   state_revision=None):
    """权威世界快照。payload 结构 M6 再收紧。"""
    message = _base(C.MSG_SNAPSHOT)
    message['round_id'] = _exact_int(round_id, 'round_id', low=0)
    message['server_tick'] = _exact_int(server_tick, 'server_tick', low=0)
    message['server_time_ms'] = _exact_int(
        server_time_ms, 'server_time_ms', low=0)
    if state_revision is not None:
        message['state_revision'] = _exact_int(
            state_revision, 'state_revision', low=0)
    message['payload'] = payload if payload is not None else {}
    return message


def build_events(round_id, events, server_time_ms=None):
    if not isinstance(events, (list, tuple)):
        raise ProtocolError('events must be a list')
    message = _base(C.MSG_EVENTS)
    message['round_id'] = _exact_int(round_id, 'round_id', low=0)
    message['events'] = list(events)
    if server_time_ms is not None:
        message['server_time_ms'] = _exact_int(
            server_time_ms, 'server_time_ms', low=0)
    return message


def build_error(code, message_text, close=False):
    message = {
        'type': C.MSG_ERROR,
        'code': _optional_text(code, 'code', 64) or '',
        'message': _optional_text(message_text, 'message', 256) or '',
    }
    if close:
        message['close'] = True
    return message


def build_pong(seq, client_time=None, server_time=None):
    message = {
        'type': C.MSG_PONG,
        'seq': _exact_int(seq, 'seq', low=0),
    }
    if client_time is not None:
        message['client_time'] = _finite_float(client_time, 'client_time')
    if server_time is not None:
        message['server_time'] = _finite_float(server_time, 'server_time')
    return message


def build_start_denied(reason, message_text=None):
    return {
        'type': C.MSG_START_DENIED,
        'reason': _optional_text(reason, 'reason', 64) or '',
        'message': _optional_text(message_text, 'message', 256) or '',
    }


def build_team_denied(team, reason):
    return {
        'type': C.MSG_TEAM_DENIED,
        'team': _exact_int(team, 'team', low=0, high=2),
        'reason': _optional_text(reason, 'reason', 64) or '',
    }


# --- 校验 -------------------------------------------------------------------


def _require_phase(phase):
    if phase not in C.PHASES:
        raise ProtocolError('invalid phase: %s' % phase)
    return phase


def validate_message(message):
    """轻量校验：必须是 dict，type 已知；返回 type 字符串。"""
    return _require_type(dict(message) if isinstance(message, dict)
                         else message)


def message_type_of(message):
    """安全读取 type；非 dict / 非文本 / 缺失时返回 None。"""
    if not isinstance(message, dict):
        return None
    kind = message.get('type')
    if isinstance(kind, bytes):
        try:
            kind = kind.decode('ascii')
        except UnicodeDecodeError:
            return None
    if kind is None:
        return None
    if not isinstance(kind, str):
        try:
            if not isinstance(kind, unicode):  # noqa: F821
                return None
        except NameError:
            return None
    if not kind:
        return None
    return kind


def is_state_barrier(message):
    kind = message_type_of(message)
    return kind in C.STATE_BARRIER_TYPES


def is_ordered_receive(message):
    kind = message_type_of(message)
    return kind in C.ORDERED_RECEIVE_TYPES
