# -*- coding: utf-8 -*-
"""Unit tests — M6 Phase3 worker pose, stationary bots, catalog hash."""
from __future__ import absolute_import, division, print_function

import pytest

from protocol.constants import (
    MSG_WORKER_POSE,
    PHASE_BATTLE,
    PROTOCOL_VERSION,
    ROLE_PLAYER,
    ROLE_WORKER,
)
from protocol.messages import (
    ProtocolError,
    build_hello,
    build_worker_pose,
    message_type_of,
)
from sim_worker.room.room import Room
from sim_worker.session import vehicle_data_hash
from vvg_client.worker_authority import WorkerAuthority


def test_vehicle_data_hash_stable():
    a = vehicle_data_hash('ussr:R05_LT')
    b = vehicle_data_hash('ussr:R05_LT')
    c = vehicle_data_hash('german:PzII')
    assert a == b
    assert a != c
    assert len(a) == 8


def test_room_rejects_mismatched_catalog_hash():
    room = Room(map_name='unit_test_map')
    room.join('Alice', 'ussr:R05_LT', role=ROLE_PLAYER,
              catalog_hash='aaaa0001')
    with pytest.raises(ValueError):
        room.join('Bob', 'german:PzII', role=ROLE_PLAYER,
                  catalog_hash='aaaa0002')


def test_room_allows_different_vehicles_same_catalog():
    room = Room(map_name='unit_test_map')
    s1 = room.join('Alice', 'ussr:R05_LT', role=ROLE_PLAYER,
                   catalog_hash='aaaa0001')
    s2 = room.join('Bob', 'german:PzII', role=ROLE_PLAYER,
                   catalog_hash='aaaa0001')
    assert s1.vehicle != s2.vehicle


def test_room_allows_no_catalog_hash():
    room = Room(map_name='unit_test_map')
    room.join('Alice', 'a:v', role=ROLE_PLAYER)
    room.join('Bob', 'b:v', role=ROLE_PLAYER)
    assert room.player_count() == 2


def test_worker_pose_builder():
    message = build_worker_pose(3, [{
        'id': 1,
        'pos': [1.0, 2.0, 3.0],
        'yaw': 0.5,
        'kind': 'player',
    }])
    assert message_type_of(message) == MSG_WORKER_POSE
    assert message['protocol'] == PROTOCOL_VERSION
    assert message['round_id'] == 3
    assert message['actors'][0]['pos'] == [1.0, 2.0, 3.0]


def test_worker_pose_rejects_bad_actor():
    with pytest.raises(ProtocolError):
        build_worker_pose(1, [{'id': 0, 'pos': [0, 0, 0]}])


def test_stationary_bots_in_snapshot():
    room = Room(map_name='unit_test_map', stationary_bots=4)
    host = room.join('Host', 'ussr:R05_LT', role=ROLE_PLAYER)
    ok, result = room.try_start_battle(host.player_id)
    assert ok is True
    assert room.phase == PHASE_BATTLE
    bots = room.bots()
    assert len(bots) == 4
    payload = room.snapshot_payload()
    kinds = [row.get('kind') for row in payload['players']]
    assert kinds.count('bot') == 4
    assert kinds.count('player') == 1
    pos_before = list(bots[0].pose['position'])
    room.tick_once(0.1, 1)
    assert bots[0].pose['position'] == pos_before


def test_apply_worker_pose_updates_player_and_bot():
    room = Room(map_name='unit_test_map', stationary_bots=2)
    host = room.join('Host', 'ussr:R05_LT', role=ROLE_PLAYER)
    room.try_start_battle(host.player_id)
    bot_id = room.bots()[0].player_id
    applied = room.apply_worker_pose(room.round_id, [
        {
            'id': host.player_id,
            'pos': [11.0, 0.0, 22.0],
            'yaw': 1.5,
            'speed': 10.0,
        },
        {
            'id': bot_id,
            'pos': [5.0, 0.0, 5.0],
            'yaw': 0.0,
            'kind': 'bot',
        },
    ])
    assert applied == 2
    assert room.get(host.player_id).pose['position'] == [11.0, 0.0, 22.0]
    assert room.bots()[0].pose['position'] == [5.0, 0.0, 5.0]


def test_worker_authority_collects_roster_actors():
    class _Client(object):
        role = ROLE_WORKER
        player_id = 99
        round_id = 7
        map_name = 'training'
        roster = {
            'players': [
                {'player_id': 1, 'name': 'A', 'team': 1, 'role': 'player'},
                {'player_id': 10000, 'name': 'Bot01', 'team': 1, 'role': 'bot'},
            ],
        }
        sent = []

        def send_message(self, message):
            self.sent.append(message)
            return True

    client = _Client()
    authority = WorkerAuthority(client)
    authority.in_battle = True
    assert authority.send_pose(now=100.0) is True
    assert len(client.sent) == 1
    message = client.sent[0]
    assert message_type_of(message) == MSG_WORKER_POSE
    assert message['round_id'] == 7
    assert len(message['actors']) == 2


def test_hello_optional_catalog_fields():
    hello = build_hello('Alice', 'ussr:R05_LT')
    hello['catalog_hash'] = 'bbbb0001'
    hello['vehicle_hash'] = vehicle_data_hash('ussr:R05_LT')
    assert hello['catalog_hash'] == 'bbbb0001'
