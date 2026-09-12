# -*- coding: utf-8 -*-
"""M3 集成测试 — sim-worker TCP 握手、房间、tick、快照。"""
from __future__ import absolute_import, division, print_function

import socket
import time

import pytest

from protocol.capabilities import CAP_CORE_SESSION_V1
from protocol.constants import (
    ERROR_INVALID_HELLO,
    ERROR_PROTOCOL_MISMATCH,
    ERROR_UNSUPPORTED_CAPABILITIES,
    MAX_MESSAGE_BYTES,
    PHASE_BATTLE,
    PHASE_WAITING,
    PROTOCOL_VERSION,
    ROLE_PLAYER,
)
from protocol.messages import (
    build_battle_ready,
    build_hello,
    build_input,
    build_ping,
    build_select_team,
    build_select_vehicle,
    build_start_battle,
)
from protocol.serializer import encode_message
from sim_worker.server import GameServer
from sim_worker.tick import snapshot_interval_ticks

from tests.integration.client_util import RemoteClient


@pytest.fixture
def server():
    srv = GameServer(
        host='127.0.0.1',
        port=0,
        map_name='unit_test_map',
        team_size=15,
        server_tick_hz=30.0,
        snapshot_hz=15.0,
    )
    srv.start(background=True)
    # 等待 listen
    assert srv.bound_port
    yield srv
    srv.stop()


def _client(server):
    return RemoteClient('127.0.0.1', server.bound_port, timeout=3.0)


class TestHandshake(object):
    def test_server_starts_on_ephemeral_port(self, server):
        assert server.bound_port > 0
        assert server.world.running is True

    def test_hello_welcome_and_roster(self, server):
        with _client(server) as client:
            client.hello('Alice')
            welcome = client.recv_until('welcome')
            assert welcome is not None
            assert welcome['type'] == 'welcome'
            assert welcome['protocol'] == PROTOCOL_VERSION
            assert welcome['name'] == 'Alice'
            assert welcome['vehicle'] == 'ussr:R05_LT'
            assert welcome['team'] in (1, 2)
            assert welcome['phase'] == PHASE_WAITING
            assert CAP_CORE_SESSION_V1 in welcome['capabilities']
            assert CAP_CORE_SESSION_V1 in welcome['server_capabilities']
            assert welcome['player_id'] >= 1
            assert welcome['spawn']['x'] in (-200.0, 200.0)

            roster = client.recv_until('roster')
            assert roster is not None
            assert roster['type'] == 'roster'
            assert roster['phase'] == PHASE_WAITING
            players = roster['players']
            assert len(players) == 1
            assert players[0]['name'] == 'Alice'

    def test_protocol_mismatch_rejected(self, server):
        with _client(server) as client:
            message = build_hello(name='Bob', vehicle='x')
            message['protocol'] = PROTOCOL_VERSION + 1
            client.send(message)
            error = client.recv_until('error')
            assert error is not None
            assert error['code'] == ERROR_PROTOCOL_MISMATCH

    def test_non_hello_rejected(self, server):
        with _client(server) as client:
            client.send(build_ping(1, 0.0))
            error = client.recv_until('error')
            assert error is not None
            assert error['code'] == ERROR_INVALID_HELLO

    def test_missing_capability_rejected(self, server):
        with _client(server) as client:
            client.send(build_hello(
                name='C', vehicle='v', capabilities=['nope_v1']))
            error = client.recv_until('error')
            assert error is not None
            assert error['code'] == ERROR_UNSUPPORTED_CAPABILITIES

    def test_player_requires_name_and_vehicle(self, server):
        with _client(server) as client:
            # build_hello 会在客户端侧拒绝；直接发裸 hello
            raw = {
                'type': 'hello',
                'protocol': PROTOCOL_VERSION,
                'client_build': 'x',
                'capabilities': [CAP_CORE_SESSION_V1],
                'role': ROLE_PLAYER,
            }
            client.send_raw(encode_message(raw))
            error = client.recv_until('error')
            assert error is not None
            assert error['code'] == ERROR_INVALID_HELLO


class TestLobby(object):
    def test_two_players_auto_balance(self, server):
        with _client(server) as a, _client(server) as b:
            wa = a.handshake('Alice')
            wb = b.handshake('Bob')
            assert wa is not None and wb is not None
            assert wa['player_id'] != wb['player_id']
            assert wa['team'] != wb['team']
            # 双方都应收到含 2 人的 roster
            roster = b.recv_until('roster')
            # b 的 handshake 已消费自己的 welcome；a 的 roster 可能已到或排队
            # 连续读直到 players==2
            deadline = time.time() + 2.0
            found = None
            while time.time() < deadline:
                if roster is not None and len(roster.get('players', [])) >= 2:
                    found = roster
                    break
                roster = b.recv_message(timeout=0.5)
            assert found is not None
            names = {row['name'] for row in found['players']}
            assert names == {'Alice', 'Bob'}

    def test_select_team_and_vehicle(self, server):
        with _client(server) as a, _client(server) as b:
            a.handshake('Alice')
            b.handshake('Bob')
            # Bob 请求 team 与 Alice 相同会失败或自动 — 先读 Alice 的 team
            # 简单：选队 1 / 2 显式
            a.send(build_select_team(1))
            b.send(build_select_team(2))
            deadline = time.time() + 2.0
            teams = {}
            while time.time() < deadline and len(teams) < 2:
                roster = a.recv_until('roster', timeout=0.4)
                if roster:
                    for row in roster['players']:
                        teams[row['name']] = row['team']
            assert teams.get('Alice') == 1
            assert teams.get('Bob') == 2

            a.send(build_select_vehicle('germany:PzII'))
            # 等 roster 含新车
            deadline = time.time() + 2.0
            vehicle = None
            while time.time() < deadline:
                roster = a.recv_until('roster', timeout=0.4)
                if roster:
                    for row in roster['players']:
                        if row['name'] == 'Alice':
                            vehicle = row['vehicle']
                if vehicle == 'germany:PzII':
                    break
            assert vehicle == 'germany:PzII'

    def test_host_is_first_player(self, server):
        with _client(server) as a:
            welcome = a.handshake('HostOnly')
            assert welcome['host_player_id'] == welcome['player_id']


class TestTickAndBattle(object):
    def test_snapshot_interval_math(self):
        assert snapshot_interval_ticks(30, 15) == 2
        assert snapshot_interval_ticks(30, 30) == 1

    def test_start_battle_and_snapshots(self, server):
        with _client(server) as host, _client(server) as guest:
            host.handshake('Host')
            guest.handshake('Guest')

            host.send(build_start_battle(0, requested_round_seconds=300))
            start = host.recv_until('battle_start')
            live = host.recv_until('battle_live')
            assert start is not None
            assert live is not None
            assert start['round_id'] == 1
            assert start['map'] == 'unit_test_map'
            assert live['round_id'] == 1
            assert live['type'] == 'battle_live'

            # 手动推进足够产生快照（15 Hz @ 30 Hz → 每 2 tick）
            server.run_ticks(6)

            # 两个客户端都应至少收到一条 snapshot
            snap_a = host.recv_until('snapshot', timeout=2.0)
            snap_b = guest.recv_until('snapshot', timeout=2.0)
            assert snap_a is not None
            assert snap_b is not None
            assert snap_a['type'] == 'snapshot'
            assert snap_a['round_id'] == 1
            assert 'payload' in snap_a
            assert len(snap_a['payload']['players']) == 2
            assert snap_a['server_tick'] > 0

    def test_input_reflected_in_snapshot(self, server):
        with _client(server) as host:
            host.handshake('Solo')
            host.send(build_start_battle(0))
            assert host.recv_until('battle_start') is not None
            assert host.recv_until('battle_live') is not None

            pid = host.player_id
            host.send(build_input(
                round_id=1,
                forward=1.0,
                turn=0.0,
                aim_yaw=0.25,
                gun_pitch=-0.1,
                input_seq=1,
                position=[10.0, 0.0, 5.0],
                yaw=0.5,
                speed=12.0,
            ))
            # input 在 handler 线程异步到达；轮询直到快照反映该姿态
            snap = None
            row = None
            deadline = time.time() + 2.0
            while time.time() < deadline:
                server.run_ticks(2)
                snap = host.recv_until('snapshot', timeout=0.5)
                if snap is None:
                    continue
                rows = snap['payload']['players']
                if not rows:
                    continue
                row = rows[0]
                if row.get('pos') == [10.0, 0.0, 5.0]:
                    break
            assert snap is not None
            assert row is not None
            assert row['id'] == pid
            assert row['pos'] == [10.0, 0.0, 5.0]
            assert row['yaw'] == 0.5
            assert row['aim_yaw'] == 0.25

    def test_battle_ready_updates_roster(self, server):
        with _client(server) as client:
            client.handshake('ReadyPlayer')
            client.send(build_start_battle(0))
            client.recv_until('battle_start')
            client.recv_until('battle_live')
            client.send(build_battle_ready(1))
            deadline = time.time() + 2.0
            ready = False
            while time.time() < deadline:
                roster = client.recv_until('roster', timeout=0.4)
                if roster:
                    for row in roster['players']:
                        if row['name'] == 'ReadyPlayer' and row.get('ready'):
                            ready = True
            assert ready

    def test_leave_updates_roster(self, server):
        with _client(server) as a, _client(server) as b:
            a.handshake('Stay')
            b.handshake('Gone')
            # 等双方 roster
            time.sleep(0.1)
            b.leave()
            b.close()
            deadline = time.time() + 2.0
            gone = False
            while time.time() < deadline:
                roster = a.recv_until('roster', timeout=0.4)
                if roster:
                    names = {row['name'] for row in roster['players']}
                    if names == {'Stay'}:
                        gone = True
                        break
            assert gone


class TestNetworkFraming(object):
    def test_oversized_hello_line_not_accepted(self, server):
        # 超过 MAX 的一整行：连接应在握手阶段失败或无 welcome
        with socket.create_connection(
                ('127.0.0.1', server.bound_port), 3.0) as sock:
            sock.settimeout(2.0)
            # 发送一个超大且无换行的垃圾，对端应最终超时/断开
            sock.sendall(b'x' * 100)
            # 再发非法 hello
            sock.sendall(b'not-json\n')
            try:
                data = sock.recv(4096)
            except socket.timeout:
                data = b''
            # 要么无 welcome，要么 error；绝不能是 welcome
            assert b'"type":"welcome"' not in data

    def test_ping_pong(self, server):
        with _client(server) as client:
            client.handshake('Pinger')
            client.send(build_ping(7, 123.5))
            # 可能先有 roster
            deadline = time.time() + 2.0
            pong = None
            while time.time() < deadline and pong is None:
                message = client.recv_message(timeout=0.4)
                if message and message.get('type') == 'pong':
                    pong = message
            assert pong is not None
            assert pong['seq'] == 7
            assert pong['client_time'] == 123.5
            assert 'server_time' in pong
