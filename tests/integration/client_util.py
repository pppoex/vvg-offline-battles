# -*- coding: utf-8 -*-
"""集成测试辅助 — 极简 JSON lines 客户端。"""
from __future__ import absolute_import, division, print_function

import socket
import time

from protocol.constants import PROTOCOL_VERSION
from protocol.messages import (
    build_hello,
    build_input,
    build_leave,
    build_ping,
    build_select_team,
    build_select_vehicle,
    build_start_battle,
    build_battle_ready,
)
from protocol.serializer import LineDecoder, encode_message


class RemoteClient(object):
    """阻塞式测试客户端（非线程）。"""

    def __init__(self, host, port, timeout=5.0):
        self.host = host
        self.port = int(port)
        self.sock = socket.create_connection((self.host, self.port), timeout)
        self.sock.settimeout(timeout)
        self.decoder = LineDecoder()
        self._inbox = []
        self.player_id = None
        self.welcome = None

    def send(self, message):
        self.sock.sendall(encode_message(message))

    def send_raw(self, payload):
        self.sock.sendall(payload)

    def recv_message(self, timeout=5.0):
        if self._inbox:
            return self._inbox.pop(0)
        deadline = time.time() + timeout
        while True:
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                return None
            if not chunk:
                return None
            messages = self.decoder.feed(chunk)
            if messages:
                self._inbox.extend(messages)
                return self._inbox.pop(0)
            if time.time() >= deadline:
                return None

    def recv_until(self, message_type, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = self.recv_message(timeout=max(0.05, deadline - time.time()))
            if message is None:
                return None
            if message.get('type') == message_type:
                return message
        return None

    def recv_all(self, count, timeout=5.0):
        out = []
        for _ in range(int(count)):
            message = self.recv_message(timeout=timeout)
            if message is None:
                break
            out.append(message)
        return out

    def hello(self, name, vehicle='ussr:R05_LT', role='player',
              capabilities=None, **kwargs):
        message = build_hello(
            name=name, vehicle=vehicle, role=role,
            capabilities=capabilities, **kwargs)
        self.send(message)
        return message

    def handshake(self, name, **kwargs):
        self.hello(name, **kwargs)
        welcome = self.recv_until('welcome')
        if welcome is not None:
            self.welcome = welcome
            self.player_id = welcome.get('player_id')
        return welcome

    def ping(self, seq=1, client_time=None):
        self.send(build_ping(seq, client_time if client_time is not None else time.time()))

    def leave(self):
        try:
            self.send(build_leave())
        except OSError:
            pass

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
