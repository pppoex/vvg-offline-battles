# -*- coding: utf-8 -*-
"""会话 — 一条已通过握手（或仍在握手）的客户端连接上的玩家身份。"""
from __future__ import absolute_import, division, print_function

import threading
import time


class PlayerSession(object):
    """一个玩家连接的权威侧记录。

    ``send`` 由服务器注入（线程安全）；``last_input`` 仅作 M3 快照占位，
    M6 再换成真正的权威运动状态。
    """

    def __init__(self, player_id, name, vehicle, team, capabilities,
                 client_build=None, max_health=None, account_key=None,
                 peer=None):
        self.player_id = int(player_id)
        self.name = name
        self.vehicle = vehicle
        self.team = int(team)
        self.capabilities = list(capabilities or ())
        self.client_build = client_build
        self.max_health = max_health
        self.account_key = account_key
        self.peer = peer
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
        """把 input 信封写入本地占位姿态（服务器权威在 M6 完善）。"""
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

    def snapshot_row(self):
        return {
            'id': self.player_id,
            'name': self.name,
            'vehicle': self.vehicle,
            'team': self.team,
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
        }
