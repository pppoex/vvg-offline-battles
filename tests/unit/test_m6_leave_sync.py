# -*- coding: utf-8 -*-
"""Unit tests — Offline leave notifies server (web garage sync)."""
from __future__ import absolute_import, division, print_function

from vvg_client.session import ClientSession


class _FakeClient(object):
    def __init__(self):
        self.connected = True
        self.phase = 'battle'
        self.round_id = 3
        self.player_id = 1
        self.host_player_id = 1
        self.map_name = 'vvg_default'
        self.sent = []

    def send_leave_battle(self, round_id=None):
        self.sent.append(round_id if round_id is not None else self.round_id)
        return True


def test_notify_offline_leave_sends_leave_battle(monkeypatch):
    session = ClientSession('Alice', 'ussr:R05_LT', host='127.0.0.1', port=1)
    fake = _FakeClient()
    session.client = fake
    session._offline_was_in_battle = True
    session._leave_notified = False

    monkeypatch.setattr(
        session, '_offline_in_battle_now', lambda: False)
    assert session.notify_offline_leave_if_needed() is True
    assert fake.sent == [3]
    assert session._leave_notified is True
    # second call should not re-send
    assert session.notify_offline_leave_if_needed() is False
    assert fake.sent == [3]
