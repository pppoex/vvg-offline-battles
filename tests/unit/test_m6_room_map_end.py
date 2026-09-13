# -*- coding: utf-8 -*-
"""Unit tests — M6 room map selection and auto battle end."""
from __future__ import absolute_import, division, print_function

import time

from protocol.constants import (
    KNOWN_ROOM_MAPS,
    MSG_SELECT_MAP,
    PHASE_BATTLE,
    PHASE_WAITING,
    PROTOCOL_VERSION,
    ROLE_PLAYER,
)
from protocol.messages import (
    build_select_map,
    build_start_battle,
    message_type_of,
)
from sim_worker.room.room import Room, is_known_map, normalize_map_name


def test_normalize_and_known_map():
    assert normalize_map_name('ensk') == '06_ensk'
    assert normalize_map_name('training') == 'training'
    assert is_known_map('06_ensk')
    assert is_known_map('vvg_default')
    assert not is_known_map('not_a_real_map')


def test_select_map_builder():
    message = build_select_map('06_ensk')
    assert message_type_of(message) == MSG_SELECT_MAP
    assert message['protocol'] == PROTOCOL_VERSION
    assert message['map_name'] == '06_ensk'


def test_start_battle_builder_accepts_map():
    message = build_start_battle(0, map_name='01_karelia')
    assert message.get('map') == '01_karelia'


def test_room_set_map_host_only():
    room = Room(map_name='vvg_default')
    host = room.join('Alice', 'ussr:R05_LT', role=ROLE_PLAYER)
    guest = room.join('Bob', 'ussr:R05_LT', role=ROLE_PLAYER)
    assert room.set_map(guest.player_id, '06_ensk') == (False, 'not_host')
    assert room.set_map(host.player_id, 'nope') == (False, 'unknown_map')
    assert room.set_map(host.player_id, '06_ensk') == (True, '')
    assert room.map_name == '06_ensk'
    # cannot change map mid-battle
    room.try_start_battle(host.player_id, round_seconds=60)
    assert room.phase == PHASE_BATTLE
    assert room.set_map(host.player_id, '01_karelia') == (False, 'not_waiting')


def test_room_auto_end_time_limit():
    room = Room(map_name='vvg_default')
    host = room.join('Alice', 'ussr:R05_LT', role=ROLE_PLAYER)
    ok, _ = room.try_start_battle(host.player_id, round_seconds=1)
    assert ok
    assert room.phase == PHASE_BATTLE
    room.battle_started_at = time.time() - 5.0
    room.battle_duration_seconds = 1.0
    reason = room.tick_once(0.1, 1)
    assert reason == 'time_limit'
    assert room.phase == PHASE_WAITING
    assert room.last_end_reason == 'time_limit'


def test_room_auto_end_no_players():
    room = Room(map_name='vvg_default')
    host = room.join('Alice', 'ussr:R05_LT', role=ROLE_PLAYER)
    room.try_start_battle(host.player_id, round_seconds=300)
    assert room.phase == PHASE_BATTLE
    host.connected = False
    reason = room.tick_once(0.1, 1)
    assert reason == 'no_players'
    assert room.phase == PHASE_WAITING


def test_roster_includes_known_maps():
    room = Room(map_name='vvg_default')
    host = room.join('Alice', 'ussr:R05_LT', role=ROLE_PLAYER)
    fields = room.welcome_fields(host)
    assert fields['known_maps'] == list(KNOWN_ROOM_MAPS)
    assert fields['map'] == 'vvg_default'
