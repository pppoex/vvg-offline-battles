# -*- coding: utf-8 -*-
"""Unit tests — M6 Phase4 remote scene + leave_battle."""
from __future__ import absolute_import, division, print_function

from protocol.constants import PHASE_BATTLE, PHASE_WAITING
from vvg_client.presentation.remote_scene import RemoteEntity, RemoteScene
from vvg_client.session import ClientSession


def test_remote_scene_spawns_and_updates():
    scene = RemoteScene(local_player_id=1)
    scene.apply_sample({
        2: {
            'id': 2,
            'pos': [1.0, 0.0, 2.0],
            'yaw': 0.5,
            'team': 2,
            'kind': 'player',
            'name': 'Bob',
            'vehicle': 'v',
        },
        10000: {
            'id': 10000,
            'pos': [5.0, 0.0, 0.0],
            'kind': 'bot',
            'team': 1,
        },
    })
    assert scene.active is True
    assert len(scene.entities()) == 2
    assert scene.get(1) is None  # local excluded
    bob = scene.get(2)
    assert bob.position == [1.0, 0.0, 2.0]
    bot = scene.get(10000)
    assert bot.kind == 'bot'

    scene.apply_sample({
        2: {'id': 2, 'pos': [3.0, 0.0, 4.0], 'yaw': 1.0},
        10000: {'id': 10000, 'pos': [5.0, 0.0, 0.0], 'kind': 'bot'},
    })
    assert scene.get(2).position == [3.0, 0.0, 4.0]
    assert scene.get(2).updates == 2


def test_remote_scene_clear():
    scene = RemoteScene(local_player_id=None)
    scene.apply_sample({9: {'id': 9, 'pos': [0, 0, 0]}})
    assert len(scene.entities()) == 1
    scene.clear()
    assert scene.entities() == []
    assert scene.active is False


def test_remote_entity_to_dict():
    entity = RemoteEntity(7, {'kind': 'bot', 'team': 2, 'name': 'B'})
    entity.apply_pose({'pos': [1, 2, 3], 'yaw': 0.25})
    data = entity.to_dict()
    assert data['id'] == 7
    assert data['pos'] == [1.0, 2.0, 3.0]
    assert data['kind'] == 'bot'


def test_session_leave_battle_clears_scene():
    session = ClientSession('Solo', 's:v', host='127.0.0.1', port=1)
    session.remote_scene.apply_sample({
        99: {'id': 99, 'pos': [1, 0, 1]},
    })
    assert len(session.remote_scene.entities()) == 1
    session.client.round_id = 3
    # offline battle import fails outside game — leave_battle still clears
    assert session.leave_battle() is True
    assert session.remote_scene.entities() == []
    assert len(session.snapshots) == 0


def test_session_phase_transition_clears_remote():
    session = ClientSession('Solo', 's:v', host='127.0.0.1', port=1)
    session.client.phase = PHASE_BATTLE
    session.client.round_id = 1
    session._last_phase = PHASE_BATTLE
    session.remote_scene.apply_sample({
        5: {'id': 5, 'pos': [0, 0, 0]},
    })
    session.client.phase = PHASE_WAITING
    session._sync_phase_and_scene()
    assert session.remote_scene.entities() == []
