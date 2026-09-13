# -*- coding: utf-8 -*-
"""Unit tests — M6 join_gate + local room web status page."""
from __future__ import absolute_import, division, print_function

import json
import os
import sys
import threading
import time

try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import Request, urlopen

import pytest

from vvg_client import join_gate
from vvg_client.ui import join_flow
from vvg_client.webui.server import (
    DEFAULT_PORT,
    StatusWebServer,
    WebController,
    find_free_port,
    render_status_html,
)


class _FakeClient(object):
    def __init__(self, host=False, connected=True):
        self.name = 'Alice'
        self.vehicle = 'ussr:R05_LT'
        self.player_id = 1
        self.host_player_id = 1 if host else 2
        self.phase = 'waiting'
        self.round_id = 0
        self.map_name = 'training'
        self.connected = connected
        self.team = 1
        self.roster = {
            'players': [
                {
                    'player_id': 1,
                    'name': 'Alice',
                    'team': 1,
                    'vehicle': 'ussr:R05_LT',
                    'ready': False,
                },
            ],
        }
        self.connection = type('C', (), {'host': '127.0.0.1', 'port': 28782})()
        self.start_calls = 0

    def is_host(self):
        return self.player_id == self.host_player_id

    def send_start_battle(self, round_seconds=None):
        self.start_calls += 1
        return True


def test_find_free_port_returns_int():
    port = find_free_port(start=19080)
    assert isinstance(port, int)
    assert port >= 19080


def test_render_status_html_contains_fields():
    html = render_status_html(
        {
            'server': '127.0.0.1:28782',
            'map': 'training',
            'phase': 'waiting',
            'round_id': 0,
            'host_player_id': 1,
            'name': 'Alice',
            'player_id': 1,
            'is_host': True,
            'connected': True,
            'players': [{'player_id': 1, 'name': 'Alice', 'team': 1,
                         'vehicle': 'x', 'ready': False}],
        },
        'http://127.0.0.1:18080/',
    )
    assert 'Alice' in html
    assert 'training' in html
    assert '开始战斗' in html


def test_web_server_status_and_start_host():
    client = _FakeClient(host=True)
    controller = WebController(client)
    server = StatusWebServer(controller, port=find_free_port(start=19100))
    url = server.start()
    try:
        resp = urlopen(url + 'status.json', timeout=2)
        body = json.loads(resp.read().decode('utf-8'))
        assert body['is_host'] is True
        assert body['map'] == 'training'

        resp = urlopen(url, timeout=2)
        html = resp.read().decode('utf-8')
        assert 'Alice' in html

        req = Request(url + 'start', data=b'', method='POST')
        # urllib2 Request may not accept method= on old py; fallback
        try:
            resp = urlopen(req, timeout=2)
        except TypeError:
            req = Request(url + 'start', data=b'')
            resp = urlopen(req, timeout=2)
        payload = json.loads(resp.read().decode('utf-8'))
        assert payload.get('ok') is True
        assert client.start_calls == 1
    finally:
        server.stop()


def test_web_server_start_forbidden_for_non_host():
    client = _FakeClient(host=False)
    controller = WebController(client)
    server = StatusWebServer(controller, port=find_free_port(start=19200))
    url = server.start()
    try:
        # POST as non-host must 403
        try:
            req = Request(url + 'start', data=b'', method='POST')
            urlopen(req, timeout=2)
            raised = None
        except Exception as exc:
            raised = exc
        # urllib raises HTTPError for 403
        assert raised is not None
        code = getattr(raised, 'code', None)
        assert code == 403
        assert client.start_calls == 0
    finally:
        server.stop()


class _FakeAccountCommands(object):
    CMD_ENQUEUE_IN_BATTLE_QUEUE = 9901
    RES_SUCCESS = 0


class _FakeFakeServer(object):
    def __init__(self):
        self._COMMANDS = {}
        self.responded = []

        def _cmdEnqueueInBattleQueue(requestID, args):
            raise AssertionError('original must not run')

        self._cmdEnqueueInBattleQueue = _cmdEnqueueInBattleQueue
        self._COMMANDS[_FakeAccountCommands.CMD_ENQUEUE_IN_BATTLE_QUEUE] = (
            _cmdEnqueueInBattleQueue)

    def _respond(self, requestID, code, text=''):
        self.responded.append((requestID, code, text))


class _FakeBattle(object):
    def __init__(self):
        self.calls = 0

    def enterRandom(self, vehInvID=None, arenaTypeID=0):
        self.calls += 1
        return True


def test_join_gate_intercepts_enqueue(monkeypatch):
    # Reset module state
    join_gate._installed = False
    join_gate._handler = None
    join_gate._orig_enqueue = None
    join_gate._orig_enter_random = None
    join_gate._fight_button = None

    fake_server = _FakeFakeServer()
    battle = _FakeBattle()
    account_commands = _FakeAccountCommands()

    # Minimal Offline package simulation
    class _Pkg(object):
        pass

    offhangar2 = _Pkg()
    offhangar2.fake_server = fake_server
    offhangar2.battle = battle

    modules = {
        'AccountCommands': account_commands,
        'gui': type(sys)('gui'),
        'gui.mods': type(sys)('gui.mods'),
        'gui.mods.offhangar2': offhangar2,
        'gui.mods.offhangar2.fake_server': fake_server,
        'gui.mods.offhangar2.battle': battle,
    }
    saved = {}
    for name, mod in modules.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    seen = []

    def handler(veh, arena):
        seen.append((veh, arena))

    try:
        join_gate.set_handler(handler)
        assert join_gate.install() is True
        # Invoke patched command
        fake_server._COMMANDS[_FakeAccountCommands.CMD_ENQUEUE_IN_BATTLE_QUEUE](
            7, [[0, 42, 0, 5]])
        assert seen == [(42, 5)]
        assert fake_server.responded and fake_server.responded[0][0] == 7
        # enterRandom fallback
        battle.enterRandom(vehInvID=9, arenaTypeID=2)
        assert seen[-1] == (9, 2)
        assert battle.calls == 0
    finally:
        join_gate.uninstall()
        join_gate.set_handler(None)
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


def test_join_flow_start_room_web():
    client = _FakeClient(host=True)
    session = type('S', (), {'client': client})()
    join_flow.stop_room_web()
    try:
        url = join_flow.start_room_web(session)
        assert url and url.startswith('http://127.0.0.1:')
        # reuse
        assert join_flow.start_room_web(session) == url
    finally:
        join_flow.stop_room_web()


def test_join_gate_fight_click_wrapper():
    join_gate._fight_button = None
    join_gate._handler = None
    seen = []
    join_gate.set_handler(lambda v, a: seen.append((v, a)))
    result = join_gate._wrapped_fight_click(None, map_id=5, action_name='random')
    assert result is None
    assert seen
    join_gate.set_handler(None)


def test_open_browser_windows_startfile(monkeypatch):
    calls = []

    def fake_startfile(url):
        calls.append(url)

    monkeypatch.setattr(os, 'name', 'nt', raising=False)
    monkeypatch.setattr(os, 'startfile', fake_startfile, raising=False)
    assert join_flow.open_browser('http://127.0.0.1:18080/') is True
    assert calls == ['http://127.0.0.1:18080/']
