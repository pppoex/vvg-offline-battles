# -*- coding: utf-8 -*-
"""BattleClient — protocol session on top of TcpLineConnection.

Reuses ``src/protocol`` builders exclusively (hello / input / ping / ...).
Owner thread must call ``pump()`` regularly (BigWorld callback or tests).
"""
from __future__ import absolute_import, division, print_function

import time

from protocol.capabilities import DEFAULT_CLIENT_CAPABILITIES
from protocol.constants import (
    CLIENT_BUILD,
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
    MSG_BATTLE_LIVE,
    MSG_BATTLE_START,
    MSG_ERROR,
    MSG_EVENTS,
    MSG_PONG,
    MSG_ROSTER,
    MSG_SNAPSHOT,
    MSG_WELCOME,
    PHASE_WAITING,
)
from protocol.messages import (
    build_battle_ready,
    build_hello,
    build_input,
    build_leave,
    build_leave_battle,
    build_ping,
    build_select_team,
    build_select_vehicle,
    build_start_battle,
    message_type_of,
)

from .connection import TcpLineConnection, monotonic_time


class BattleClient(object):
    """Thin-client protocol session.

    Lifecycle::

        client = BattleClient('Alice', 'ussr:R05_LT', host, port)
        assert client.connect_and_handshake()
        while client.connected:
            client.pump()
            # ... render / predict ...
        client.disconnect()
    """

    def __init__(self, name, vehicle, host=None, port=None,
                 capabilities=None, client_build=None, account_key=None,
                 max_health=None, requested_team=None, poll_limit=64):
        self.name = name
        self.vehicle = vehicle
        self.client_build = client_build or CLIENT_BUILD
        self.account_key = account_key
        self.max_health = max_health
        self.requested_team = requested_team
        if capabilities is None:
            self.capabilities = list(DEFAULT_CLIENT_CAPABILITIES)
        else:
            self.capabilities = list(capabilities)
        self.poll_limit = int(poll_limit)

        if host is None or port is None:
            host, port = self._default_address()
        self.connection = TcpLineConnection(host, port, name='battle-client')

        self.welcome = None
        self.roster = None
        self.last_snapshot = None
        self.last_error = None
        self.server_capabilities = []
        self.shared_capabilities = []
        self.round_id = 0
        self.phase = PHASE_WAITING
        self.player_id = None
        self.team = None
        self.host_player_id = None
        self.map_name = None
        self.state_revision = 0
        self.spawn = None
        self.last_pong = None
        self.last_events = []
        self.snapshots_received = 0
        self._input_seq = 0
        self._ping_seq = 0
        self._fire_seq = 0
        self._started_at = monotonic_time()
        self._handlers = {
            MSG_WELCOME: self._on_welcome,
            MSG_ROSTER: self._on_roster,
            MSG_BATTLE_START: self._on_battle_start,
            MSG_BATTLE_LIVE: self._on_battle_live,
            MSG_SNAPSHOT: self._on_snapshot,
            MSG_EVENTS: self._on_events,
            MSG_PONG: self._on_pong,
            MSG_ERROR: self._on_error,
        }

    @staticmethod
    def _default_address():
        try:
            from sdk import config
            return config.get_server_address()
        except Exception:
            return (DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT)

    # --- 连接 / 握手 --------------------------------------------------------

    @property
    def connected(self):
        return self.connection.connected

    def build_hello_message(self):
        return build_hello(
            name=self.name,
            vehicle=self.vehicle,
            capabilities=self.capabilities,
            client_build=self.client_build,
            account_key=self.account_key,
            max_health=self.max_health,
            requested_team=self.requested_team,
        )

    def connect(self, timeout=3.0, send_hello=True):
        """Open TCP and optionally send hello as the first wire message."""
        if not self.connection.open(timeout=timeout):
            self.last_error = self.connection.last_error
            return False
        if not send_hello:
            return True
        if not self.connection.send_message(self.build_hello_message()):
            self.last_error = self.connection.last_error
            return False
        return True

    def handshake(self, timeout=5.0):
        """Pump until welcome (or error / timeout). Returns welcome dict."""
        deadline = monotonic_time() + float(timeout)
        while monotonic_time() < deadline:
            self.pump()
            if self.welcome is not None:
                return self.welcome
            # Server sent a fatal handshake error (or peer closed).
            if self.last_error is not None:
                return None
            if not self.connection.connected:
                return None
            time.sleep(0.01)
        return None

    def connect_and_handshake(self, timeout=5.0):
        if not self.connect():
            return None
        return self.handshake(timeout=timeout)

    def disconnect(self, polite=True):
        if polite and self.connection.connected:
            try:
                self.connection.send_message(build_leave())
            except Exception:
                pass
        return self.connection.close()

    # --- pump ---------------------------------------------------------------

    def pump(self, max_messages=None):
        """Consume inbound frames and update session state. Returns count."""
        limit = self.poll_limit if max_messages is None else int(max_messages)
        messages = self.connection.poll(max_messages=limit)
        for message in messages:
            self._dispatch(message)
        if not self.connection.connected and self.last_error is None:
            self.last_error = self.connection.last_error
        return len(messages)

    def _dispatch(self, message):
        kind = message_type_of(message)
        if kind is None:
            return
        handler = self._handlers.get(kind)
        if handler is not None:
            handler(message)

    def _on_welcome(self, message):
        self.welcome = message
        self.player_id = message.get('player_id')
        self.team = message.get('team')
        self.phase = message.get('phase', PHASE_WAITING)
        self.round_id = int(message.get('round_id') or 0)
        self.map_name = message.get('map')
        self.state_revision = int(message.get('state_revision') or 0)
        self.host_player_id = message.get('host_player_id')
        self.spawn = message.get('spawn')
        self.server_capabilities = list(message.get('server_capabilities') or ())
        # Negotiated list as echoed by the server.
        self.shared_capabilities = list(message.get('capabilities') or ())

    def _on_roster(self, message):
        self.roster = message
        if 'phase' in message:
            self.phase = message['phase']
        if 'round_id' in message:
            self.round_id = int(message['round_id'] or 0)
        if 'state_revision' in message:
            self.state_revision = int(message['state_revision'] or 0)
        if 'host_player_id' in message:
            self.host_player_id = message['host_player_id']

    def _on_battle_start(self, message):
        if 'round_id' in message:
            self.round_id = int(message['round_id'] or 0)
        if 'map' in message:
            self.map_name = message['map']
        if 'state_revision' in message:
            self.state_revision = int(message['state_revision'] or 0)

    def _on_battle_live(self, message):
        if 'round_id' in message:
            self.round_id = int(message['round_id'] or 0)
        if 'state_revision' in message:
            self.state_revision = int(message['state_revision'] or 0)

    def _on_snapshot(self, message):
        self.last_snapshot = message
        self.snapshots_received += 1
        if 'round_id' in message:
            self.round_id = int(message['round_id'] or 0)

    def _on_events(self, message):
        self.last_events = list(message.get('events') or ())

    def _on_pong(self, message):
        self.last_pong = message

    def _on_error(self, message):
        self.last_error = '%s: %s' % (
            message.get('code', 'error'), message.get('message', ''))

    # --- 出站便捷 API -------------------------------------------------------

    def send_message(self, message):
        return self.connection.send_message(message)

    def send_input(self, forward=0.0, turn=0.0, aim_yaw=0.0, gun_pitch=0.0,
                   position=None, yaw=None, pitch=None, roll=None, speed=None,
                   fire_seq=None, advance_seq=True):
        """Send one input frame; increments input_seq by default."""
        if fire_seq is None:
            fire_seq = self._fire_seq
        message = build_input(
            round_id=self.round_id,
            forward=forward,
            turn=turn,
            aim_yaw=aim_yaw,
            gun_pitch=gun_pitch,
            input_seq=self._input_seq,
            position=position,
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            speed=speed,
            fire_seq=fire_seq,
        )
        if advance_seq:
            self._input_seq += 1
        return self.send_message(message)

    def send_ping(self):
        self._ping_seq += 1
        return self.send_message(build_ping(self._ping_seq, time.time()))

    def send_start_battle(self, round_seconds=None):
        return self.send_message(
            build_start_battle(self.round_id, requested_round_seconds=round_seconds))

    def send_battle_ready(self, round_id=None):
        rid = self.round_id if round_id is None else round_id
        return self.send_message(build_battle_ready(rid))

    def send_select_vehicle(self, vehicle, max_health=None):
        return self.send_message(
            build_select_vehicle(vehicle, max_health=max_health))

    def send_select_team(self, team):
        return self.send_message(build_select_team(team))

    def send_leave_battle(self, round_id=None):
        rid = self.round_id if round_id is None else round_id
        return self.send_message(build_leave_battle(rid))

    # --- 视图辅助 -----------------------------------------------------------

    def roster_names(self):
        if not isinstance(self.roster, dict):
            return []
        return [row.get('name') for row in (self.roster.get('players') or ())]

    def own_roster_row(self):
        if not isinstance(self.roster, dict):
            return None
        for row in self.roster.get('players') or ():
            if row.get('player_id') == self.player_id:
                return row
        return None

    def snapshot_player_row(self, player_id=None):
        if not isinstance(self.last_snapshot, dict):
            return None
        payload = self.last_snapshot.get('payload') or {}
        rows = payload.get('players') or ()
        wanted = self.player_id if player_id is None else player_id
        for row in rows:
            if row.get('id') == wanted:
                return row
        return None

    def is_host(self):
        return (self.player_id is not None
                and self.player_id == self.host_player_id)


__all__ = ['BattleClient']
