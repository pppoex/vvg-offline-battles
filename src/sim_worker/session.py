# -*- coding: utf-8 -*-
"""会话 — 一条已通过握手（或仍在握手）的客户端连接上的玩家/worker 身份。"""
from __future__ import absolute_import, division, print_function

import threading
import time


def vehicle_data_hash(vehicle):
    """Stable short hash of a vehicle compact descr / id string (M6 consistency)."""
    if vehicle is None:
        return ''
    if isinstance(vehicle, bytes):
        text = vehicle
    else:
        try:
            text = vehicle.encode('utf-8')
        except Exception:
            text = str(vehicle).encode('utf-8')
    # FNV-1a 32-bit
    result = 2166136261
    for byte in bytearray(text):
        result ^= byte
        result = (result * 16777619) & 0xFFFFFFFF
    return '%08x' % result


class PlayerSession(object):
    """一个玩家连接的权威侧记录。

    ``send`` 由服务器注入（线程安全）；``pose`` 在 M6 由 worker 提案覆盖。
    """

    def __init__(self, player_id, name, vehicle, team, capabilities,
                 client_build=None, max_health=None, account_key=None,
                 peer=None, role='player', vehicle_hash=None):
        self.player_id = int(player_id)
        self.name = name
        self.vehicle = vehicle
        self.team = int(team)
        self.capabilities = list(capabilities or ())
        self.client_build = client_build
        self.max_health = max_health
        self.account_key = account_key
        self.peer = peer
        self.role = role or 'player'
        self.vehicle_hash = (
            vehicle_hash if vehicle_hash is not None
            else vehicle_data_hash(vehicle))
        self.joined_at = time.time()
        self.connected = True
        self.ready = False
        self.ready_round_id = None
        self.last_input = None
        self.pose = {
            'position': [0.0, 0.0, 0.0],
            'yaw': 0.0,
            'aim_yaw': 0.0,
            'gun_pitch': 0.0,
            'speed': 0.0,
        }
        self._send_lock = threading.Lock()
        self._send_fn = None

    def bind_send(self, send_fn):
        """注入线程安全发送函数；send_fn(message_dict) -> bool。"""
        with self._send_lock:
            self._send_fn = send_fn

    def send(self, message):
        """发送一条消息；断开或失败返回 False。"""
        with self._send_lock:
            send_fn = self._send_fn
            if not self.connected or send_fn is None:
                return False
            try:
                return bool(send_fn(message))
            except Exception:
                self.connected = False
                return False

    def mark_disconnected(self):
        self.connected = False

    def apply_input(self, message):
        """把 input 信封写入本地占位姿态（worker 提案优先时可被覆盖）。"""
        self.last_input = message
        position = message.get('position')
        if isinstance(position, (list, tuple)) and len(position) == 3:
            self.pose['position'] = [float(position[0]),
                                     float(position[1]),
                                     float(position[2])]
        if message.get('yaw') is not None:
            self.pose['yaw'] = float(message['yaw'])
        if message.get('aim_yaw') is not None:
            self.pose['aim_yaw'] = float(message['aim_yaw'])
        if message.get('gun_pitch') is not None:
            self.pose['gun_pitch'] = float(message['gun_pitch'])
        if message.get('speed') is not None:
            self.pose['speed'] = float(message['speed'])

    def apply_pose(self, actor):
        """Apply a worker pose proposal row."""
        position = actor.get('pos')
        if isinstance(position, (list, tuple)) and len(position) == 3:
            self.pose['position'] = [float(position[0]),
                                     float(position[1]),
                                     float(position[2])]
        if actor.get('yaw') is not None:
            self.pose['yaw'] = float(actor['yaw'])
        if actor.get('aim_yaw') is not None:
            self.pose['aim_yaw'] = float(actor['aim_yaw'])
        if actor.get('gun_pitch') is not None:
            self.pose['gun_pitch'] = float(actor['gun_pitch'])
        if actor.get('speed') is not None:
            self.pose['speed'] = float(actor['speed'])

    def snapshot_row(self):
        return {
            'id': self.player_id,
            'name': self.name,
            'vehicle': self.vehicle,
            'team': self.team,
            'kind': 'player',
            'pos': list(self.pose['position']),
            'yaw': self.pose['yaw'],
            'aim_yaw': self.pose['aim_yaw'],
            'gun_pitch': self.pose['gun_pitch'],
            'speed': self.pose['speed'],
        }

    def roster_row(self):
        return {
            'player_id': self.player_id,
            'name': self.name,
            'vehicle': self.vehicle,
            'team': self.team,
            'ready': bool(self.ready),
            'connected': bool(self.connected),
            'role': self.role,
            'vehicle_hash': self.vehicle_hash,
        }


class BotSlot(object):
    """M6 原地 Bot：固定出生点，不移动、不开火。"""

    def __init__(self, bot_id, name, vehicle, team, pose):
        self.player_id = int(bot_id)
        self.name = name
        self.vehicle = vehicle
        self.team = int(team)
        self.kind = 'bot'
        self.pose = {
            'position': [float(pose.get('x', 0.0)),
                         float(pose.get('y', 0.0)),
                         float(pose.get('z', 0.0))],
            'yaw': float(pose.get('yaw', 0.0)),
            'aim_yaw': float(pose.get('yaw', 0.0)),
            'gun_pitch': 0.0,
            'speed': 0.0,
        }

    def snapshot_row(self):
        return {
            'id': self.player_id,
            'name': self.name,
            'vehicle': self.vehicle,
            'team': self.team,
            'kind': 'bot',
            'pos': list(self.pose['position']),
            'yaw': self.pose['yaw'],
            'aim_yaw': self.pose['aim_yaw'],
            'gun_pitch': self.pose['gun_pitch'],
            'speed': 0.0,
        }

    def roster_row(self):
        return {
            'player_id': self.player_id,
            'name': self.name,
            'vehicle': self.vehicle,
            'team': self.team,
            'ready': True,
            'connected': True,
            'role': 'bot',
            'vehicle_hash': vehicle_data_hash(self.vehicle),
        }

    def apply_pose(self, actor):
        position = actor.get('pos')
        if isinstance(position, (list, tuple)) and len(position) == 3:
            self.pose['position'] = [float(position[0]),
                                     float(position[1]),
                                     float(position[2])]
        if actor.get('yaw') is not None:
            self.pose['yaw'] = float(actor['yaw'])
        if actor.get('aim_yaw') is not None:
            self.pose['aim_yaw'] = float(actor['aim_yaw'])
        if actor.get('gun_pitch') is not None:
            self.pose['gun_pitch'] = float(actor['gun_pitch'])
