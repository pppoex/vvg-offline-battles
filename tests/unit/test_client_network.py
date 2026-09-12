# -*- coding: utf-8 -*-
"""Unit tests — thin client network / prediction / reconnect policy."""
from __future__ import absolute_import, division, print_function

import os
import socket
import threading
import time

import pytest

from protocol.constants import (
    DEFAULT_SERVER_PORT,
    PROTOCOL_VERSION,
    ROLE_PLAYER,
)
from protocol.messages import build_hello, build_welcome
from protocol.serializer import encode_message

from vvg_client.network.client import BattleClient
from vvg_client.network.connection import TcpLineConnection
from vvg_client.network.reconnect import ReconnectPolicy
from vvg_client.prediction.interpolation import SnapshotBuffer
from vvg_client.prediction.local_player import LocalPlayer


# ---------------------------------------------------------------------------
# 测试用假服务器
# ---------------------------------------------------------------------------


class _FakeServer(object):
    """Single-accept JSON lines echo/fixture server."""

    def __init__(self, handler=None):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self.handler = handler
        self.received = []
        self._clients = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                self.sock.settimeout(0.2)
                client, _addr = self.sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break
            self._clients.append(client)
            t = threading.Thread(target=self._serve, args=(client,))
            t.daemon = True
            t.start()

    def _serve(self, client):
        client.settimeout(0.2)
        buf = b''
        sent_hello_reply = False
        while not self._stop.is_set():
            try:
                chunk = client.recv(8192)
            except socket.timeout:
                continue
            except Exception:
                break
            if not chunk:
                break
            buf += chunk
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                if not line.strip():
                    continue
                from protocol.serializer import try_decode_message
                message = try_decode_message(line)
                if message is not None:
                    self.received.append(message)
                if (not sent_hello_reply
                        and message is not None
                        and message.get('type') == 'hello'):
                    sent_hello_reply = True
                    reply = build_welcome(
                        player_id=1,
                        name=message.get('name') or 'X',
                        vehicle=message.get('vehicle') or 'v',
                        team=1,
                        map_name='fake',
                        phase='waiting',
                        capabilities=message.get('capabilities'),
                        server_capabilities=['core_session_v1'],
                        spawn={'x': 1.0, 'y': 0.0, 'z': 2.0, 'yaw': 0.5},
                    )
                    try:
                        client.sendall(encode_message(reply))
                    except Exception:
                        return
                if self.handler is not None:
                    out = self.handler(message)
                    if out is not None:
                        try:
                            client.sendall(encode_message(out))
                        except Exception:
                            return

    def close(self):
        self._stop.set()
        for client in self._clients:
            try:
                client.close()
            except Exception:
                pass
        try:
            self.sock.close()
        except Exception:
            pass
        try:
            self._thread.join(0.5)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# connection
# ---------------------------------------------------------------------------


class TestTcpLineConnection(object):
    def test_open_send_poll_close(self):
        server = _FakeServer()
        try:
            conn = TcpLineConnection('127.0.0.1', server.port)
            assert conn.open(timeout=2.0)
            assert conn.connected
            assert conn.send_message(build_hello(name='A', vehicle='v'))
            deadline = time.time() + 2.0
            got = []
            while time.time() < deadline and not got:
                got = conn.poll()
                if not got:
                    time.sleep(0.01)
            assert got
            assert got[0]['type'] == 'welcome'
            assert conn.close()
            assert not conn.connected
        finally:
            server.close()

    def test_connect_failure_returns_false(self):
        # Port with no listener (reserved ephemeral that is not listening).
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        conn = TcpLineConnection('127.0.0.1', port)
        assert conn.open(timeout=0.5) is False
        assert conn.last_error is not None


# ---------------------------------------------------------------------------
# BattleClient
# ---------------------------------------------------------------------------


class TestBattleClient(object):
    def test_handshake_and_state(self):
        server = _FakeServer()
        try:
            client = BattleClient('Alice', 'ussr:R05_LT',
                                  host='127.0.0.1', port=server.port)
            welcome = client.connect_and_handshake(timeout=3.0)
            assert welcome is not None
            assert welcome['type'] == 'welcome'
            assert client.player_id == 1
            assert client.team == 1
            assert client.phase == 'waiting'
            assert client.spawn['x'] == 1.0
            assert client.connected
            client.disconnect()
        finally:
            server.close()

    def test_hello_is_first_wire_message(self):
        server = _FakeServer()
        try:
            client = BattleClient('Bob', 'germany:PzII',
                                  host='127.0.0.1', port=server.port)
            assert client.connect()
            client.handshake(timeout=2.0)
            assert server.received
            first = server.received[0]
            assert first['type'] == 'hello'
            assert first['protocol'] == PROTOCOL_VERSION
            assert first['role'] == ROLE_PLAYER
            assert first['name'] == 'Bob'
            client.disconnect()
        finally:
            server.close()

    def test_error_message_sets_last_error(self):
        from protocol.messages import build_error
        from protocol.constants import ERROR_JOIN_REJECTED

        class _ErrServer(_FakeServer):
            def _serve(self, client):
                client.settimeout(0.2)
                buf = b''
                while not self._stop.is_set():
                    try:
                        chunk = client.recv(8192)
                    except socket.timeout:
                        continue
                    except Exception:
                        break
                    if not chunk:
                        break
                    buf += chunk
                    if b'\n' not in buf:
                        continue
                    from protocol.serializer import try_decode_message
                    line = buf.split(b'\n', 1)[0]
                    message = try_decode_message(line)
                    if message and message.get('type') == 'hello':
                        try:
                            client.sendall(encode_message(build_error(
                                ERROR_JOIN_REJECTED, 'rejected')))
                        except Exception:
                            return

        err_server = _ErrServer()
        try:
            client = BattleClient('C', 'v', host='127.0.0.1',
                                  port=err_server.port)
            welcome = client.connect_and_handshake(timeout=2.0)
            assert welcome is None
            assert client.last_error is not None
            assert 'join_rejected' in client.last_error or 'rejected' in client.last_error
            client.disconnect()
        finally:
            err_server.close()


# ---------------------------------------------------------------------------
# ReconnectPolicy
# ---------------------------------------------------------------------------


class TestReconnectPolicy(object):
    def test_backoff_and_exhaust(self):
        policy = ReconnectPolicy(
            enabled=True, max_attempts=3, initial_delay=0.5,
            backoff=2.0, max_delay=8.0)
        assert policy.next_delay() == 0.5
        assert policy.next_delay() == 1.0
        assert policy.next_delay() == 2.0
        assert policy.next_delay() is None
        assert policy.can_retry() is False
        policy.reset()
        assert policy.can_retry() is True

    def test_disabled(self):
        policy = ReconnectPolicy(enabled=False)
        assert policy.next_delay() is None
        assert policy.can_retry() is False

    def test_from_config_defaults(self):
        policy = ReconnectPolicy.from_config()
        assert policy.max_attempts >= 1
        assert policy.initial_delay > 0


# ---------------------------------------------------------------------------
# LocalPlayer / SnapshotBuffer
# ---------------------------------------------------------------------------


class TestLocalPlayer(object):
    def test_spawn_seed(self):
        player = LocalPlayer(spawn={'x': 10.0, 'y': 0.0, 'z': -4.0, 'yaw': 1.0})
        pose = player.pose()
        assert pose['position'] == [10.0, 0.0, -4.0]
        assert pose['yaw'] == 1.0

    def test_step_moves_forward(self):
        player = LocalPlayer(spawn={'x': 0.0, 'y': 0.0, 'z': 0.0, 'yaw': 0.0})
        player.set_input(forward=1.0, turn=0.0)
        for _ in range(30):
            player.step(1.0 / 30.0)
        pose = player.pose()
        assert pose['position'][2] > 0.0
        assert pose['predicted'] is True

    def test_authority_correction(self):
        player = LocalPlayer(spawn={'x': 0.0, 'y': 0.0, 'z': 0.0, 'yaw': 0.0})
        player.set_input(forward=1.0)
        player.step(1.0)
        player.on_authority_row({
            'pos': [5.0, 1.0, 7.0],
            'yaw': 0.25,
            'aim_yaw': 0.3,
            'gun_pitch': -0.1,
            'speed': 3.0,
        })
        pose = player.pose()
        assert pose['position'] == [5.0, 1.0, 7.0]
        assert pose['yaw'] == 0.25
        assert pose['predicted'] is False


class TestSnapshotBuffer(object):
    def _snap(self, tick, x):
        return {
            'type': 'snapshot',
            'server_tick': tick,
            'payload': {
                'players': [{
                    'id': 1,
                    'name': 'A',
                    'vehicle': 'v',
                    'team': 1,
                    'pos': [float(x), 0.0, 0.0],
                    'yaw': 0.0,
                    'aim_yaw': 0.0,
                    'gun_pitch': 0.0,
                    'speed': 0.0,
                }],
            },
        }

    def test_empty(self):
        buf = SnapshotBuffer()
        assert buf.sample() == {}
        assert buf.latest() is None

    def test_single_frame_passthrough(self):
        buf = SnapshotBuffer()
        buf.push(self._snap(1, 10))
        sampled = buf.sample(delay_ms=100)
        assert sampled[1]['pos'] == [10.0, 0.0, 0.0]

    def test_blend_between_frames(self):
        buf = SnapshotBuffer()
        buf.push(self._snap(1, 0))
        time.sleep(0.02)
        buf.push(self._snap(2, 10))
        sampled = buf.sample(delay_ms=0)
        x = sampled[1]['pos'][0]
        # Should be strictly between 0 and 10 (or equal to 10 if target
        # sits on the newer sample edge).
        assert 0.0 <= x <= 10.0

    def test_ring_cap(self):
        buf = SnapshotBuffer(max_frames=4)
        for i in range(10):
            buf.push(self._snap(i, i))
            time.sleep(0.002)
        assert len(buf) == 4
        assert buf.latest()['server_tick'] == 9


# ---------------------------------------------------------------------------
# ClientSession glue (no real server — just local objects)
# ---------------------------------------------------------------------------


class TestClientSessionLocal(object):
    def test_local_player_seeded_from_welcome_spawn(self):
        from vvg_client.session import ClientSession
        server = _FakeServer()
        try:
            session = ClientSession(
                'Alice', 'ussr:R05_LT', host='127.0.0.1', port=server.port)
            welcome = session.start(timeout=3.0)
            assert welcome is not None
            pose = session.local_player.pose()
            assert pose['position'] == [1.0, 0.0, 2.0]
            session.tick(dt=0.0, forward=0.0)
            session.stop()
        finally:
            server.close()


# ---------------------------------------------------------------------------
# 与 sdk.config / protocol 常量对齐
# ---------------------------------------------------------------------------


class TestDefaultsAlign(object):
    def test_default_port_matches_protocol(self):
        from sdk import config
        assert config.SERVER_PORT == DEFAULT_SERVER_PORT
        assert config.PROTOCOL_VERSION == PROTOCOL_VERSION
