# -*- coding: utf-8 -*-
"""M4 集成测试 — 薄客户端 BattleClient / ClientSession 对接真实 sim-worker。"""
from __future__ import absolute_import, division, print_function

import time

import pytest

from protocol.constants import PHASE_BATTLE, PHASE_WAITING, PROTOCOL_VERSION
from sim_worker.server import GameServer

from vvg_client.network.client import BattleClient
from vvg_client.session import ClientSession


@pytest.fixture
def server():
    srv = GameServer(
        host='127.0.0.1',
        port=0,
        map_name='m4_integ_map',
        team_size=15,
        server_tick_hz=30.0,
        snapshot_hz=15.0,
    )
    srv.start(background=True)
    assert srv.bound_port
    yield srv
    srv.stop()


def _wait(predicate, timeout=3.0, pump=None, interval=0.01):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pump is not None:
            pump()
        if predicate():
            return True
        time.sleep(interval)
    return False


class TestThinClientHandshake(object):
    def test_connect_and_handshake(self, server):
        client = BattleClient(
            'Alice', 'ussr:R05_LT', host='127.0.0.1', port=server.bound_port)
        try:
            welcome = client.connect_and_handshake(timeout=4.0)
            assert welcome is not None
            assert welcome['type'] == 'welcome'
            assert welcome['protocol'] == PROTOCOL_VERSION
            assert welcome['name'] == 'Alice'
            assert welcome['team'] in (1, 2)
            assert welcome['phase'] == PHASE_WAITING
            assert client.player_id == welcome['player_id']
            assert client.connected
            assert client.spawn is not None
        finally:
            client.disconnect()

    def test_two_clients_roster(self, server):
        a = BattleClient('Alice', 'a:v', host='127.0.0.1',
                         port=server.bound_port)
        b = BattleClient('Bob', 'b:v', host='127.0.0.1',
                         port=server.bound_port)
        try:
            assert a.connect_and_handshake(timeout=4.0) is not None
            assert b.connect_and_handshake(timeout=4.0) is not None
            assert a.player_id != b.player_id
            assert a.team != b.team

            def names_ready():
                a.pump()
                b.pump()
                return set(a.roster_names()) == {'Alice', 'Bob'}

            assert _wait(names_ready, timeout=3.0)
        finally:
            a.disconnect()
            b.disconnect()

    def test_protocol_mismatch_surfaces_error(self, server):
        client = BattleClient('Eve', 'e:v', host='127.0.0.1',
                              port=server.bound_port)
        try:
            # Open TCP only; first wire frame is a bad-protocol hello.
            assert client.connect(send_hello=False)
            message = client.build_hello_message()
            message['protocol'] = PROTOCOL_VERSION + 1
            assert client.send_message(message)
            assert client.handshake(timeout=3.0) is None
            assert client.last_error is not None
            assert 'protocol' in client.last_error.lower()
        finally:
            client.disconnect()


class TestThinClientBattleFlow(object):
    def test_start_battle_receive_snapshot_and_input(self, server):
        host = BattleClient('Host', 'h:v', host='127.0.0.1',
                            port=server.bound_port)
        try:
            assert host.connect_and_handshake(timeout=4.0) is not None
            assert host.is_host()
            assert host.send_start_battle(round_seconds=300)

            assert _wait(
                lambda: host.pump() or True,
                timeout=1.0,
                pump=host.pump,
            )
            # battle_start / battle_live
            assert _wait(
                lambda: host.round_id == 1 and host.pump() >= 0,
                timeout=2.0,
                pump=host.pump,
            )

            # 确保进入战斗相位（从 roster / 消息侧）
            server.run_ticks(4)
            assert _wait(
                lambda: host.send_battle_ready() and True,
                timeout=1.0,
                pump=host.pump,
            )

            # 发送 input 并等待快照回显
            sent = host.send_input(
                forward=1.0,
                turn=0.0,
                aim_yaw=0.4,
                gun_pitch=-0.05,
                position=[12.0, 0.0, 30.0],
                yaw=0.8,
                speed=10.0,
            )
            assert sent

            def reflected():
                server.run_ticks(2)
                host.pump()
                row = host.snapshot_player_row()
                if row is None:
                    return False
                return row.get('pos') == [12.0, 0.0, 30.0]

            assert _wait(reflected, timeout=3.0)
            assert host.snapshots_received >= 1
            assert host.last_snapshot['round_id'] == 1
            assert host.last_snapshot['server_tick'] > 0
        finally:
            host.disconnect()

    def test_session_tick_absorbs_authority(self, server):
        session = ClientSession(
            'Solo', 's:v', host='127.0.0.1', port=server.bound_port)
        try:
            welcome = session.start(timeout=4.0)
            assert welcome is not None
            assert session.local_player.pose()['position'] == [
                welcome['spawn']['x'],
                welcome['spawn']['y'],
                welcome['spawn']['z'],
            ]

            # Host starts battle and loads in.
            assert session.client.send_start_battle(round_seconds=300)

            def in_battle():
                session.tick(dt=0.0)
                return session.client.round_id == 1

            assert _wait(in_battle, timeout=2.0)
            assert session.client.send_battle_ready(1)

            # Drive local prediction + send input.
            assert session.tick(
                dt=1.0 / 30.0, forward=1.0, turn=0.0, send_input=True)

            def authority_seen():
                server.run_ticks(2)
                session.tick(dt=1.0 / 30.0, forward=1.0, send_input=False)
                return (session.client.snapshot_player_row() is not None
                        and session.client.snapshots_received >= 1)

            assert _wait(authority_seen, timeout=3.0)
            row = session.client.snapshot_player_row()
            assert row['id'] == session.player_id
            # After authority frame, local pose should match server row.
            pose = session.local_player.pose()
            assert pose['position'][0] == pytest.approx(row['pos'][0], abs=1e-6)
            assert pose['predicted'] is False
        finally:
            session.stop()

    def test_ping_pong_roundtrip(self, server):
        client = BattleClient('P', 'p:v', host='127.0.0.1',
                              port=server.bound_port)
        try:
            assert client.connect_and_handshake(timeout=4.0) is not None
            assert client.send_ping()

            def got_pong():
                client.pump()
                return client.last_pong is not None

            assert _wait(got_pong, timeout=2.0)
            assert client.last_pong['seq'] == 1
            assert client.last_pong['client_time'] is not None
        finally:
            client.disconnect()
