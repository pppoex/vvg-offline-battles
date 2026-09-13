# -*- coding: utf-8 -*-
"""Worker authority glue: enter Offline battle space and publish poses.

When the sim-worker starts a round, the hidden game worker receives
``battle_start`` and (best-effort) enters the Offline battle space so terrain
and models exist. Poses are then published as ``worker_pose`` proposals.

Without BigWorld (host tests / CLI), battle entry is skipped and a static
placeholder pose stream is sent so the protocol path stays exercised.
"""
from __future__ import absolute_import, division, print_function

import sys
import time

from protocol.messages import build_worker_pose

LOG_PREFIX = '[VVG worker_auth] '

POSE_HZ = 15.0
_MAP_ALIASES = {
    'vvg_default': '06_ensk',
    'training': '06_ensk',
    'unit_test_map': '06_ensk',
}


def _log(message):
    try:
        sys.stdout.write(LOG_PREFIX + str(message) + '\n')
        sys.stdout.flush()
    except Exception:
        pass


class WorkerAuthority(object):
    """Tracks battle space entry and sends worker_pose at a fixed rate."""

    def __init__(self, client, pose_hz=POSE_HZ):
        self.client = client
        self.pose_hz = float(pose_hz or POSE_HZ)
        self.in_battle = False
        self.space_entered = False
        self.last_pose_sent = 0.0
        self._last_round = 0

    def on_battle_start(self, message):
        round_id = int(message.get('round_id') or 0)
        map_name = message.get('map') or getattr(self.client, 'map_name', None)
        _log('battle_start round=%s map=%s' % (round_id, map_name))
        self._last_round = round_id
        self.in_battle = True
        self._enter_offline_space(map_name)

    def on_battle_live(self, message):
        if not self.in_battle:
            self.on_battle_start(message)

    def on_leave_or_waiting(self):
        if self.in_battle:
            _log('leave battle space')
        self.in_battle = False
        self.space_entered = False
        self._leave_offline_space()

    def pump(self, now=None):
        """Call from session.tick; sends pose if due and in battle."""
        if not self.in_battle:
            return False
        now = time.time() if now is None else float(now)
        interval = 1.0 / max(1.0, self.pose_hz)
        if now - self.last_pose_sent < interval:
            return False
        self.last_pose_sent = now
        return self.send_pose(now)

    def collect_actors(self):
        """Build worker_pose actor list from room roster + placeholder."""
        client = self.client
        round_id = int(getattr(client, 'round_id', 0) or 0)
        actors = []
        roster = getattr(client, 'roster', None)
        rows = []
        if isinstance(roster, dict):
            rows = list(roster.get('players') or ())
        # Local offline space sample (if any) for own avatar — not required
        sample = self._sample_local_pose()
        for row in rows:
            actor_id = row.get('player_id') or row.get('id')
            if actor_id is None:
                continue
            if sample is not None and actor_id == getattr(client, 'player_id', None):
                pos, yaw = sample
            else:
                pos = self._stable_pos(actor_id, row)
                yaw = 0.0 if row.get('role') == 'bot' else 0.1 * (actor_id % 7)
            actors.append({
                'id': int(actor_id),
                'pos': pos,
                'yaw': yaw,
                'aim_yaw': yaw,
                'gun_pitch': 0.0,
                'speed': 0.0,
                'kind': row.get('role') or row.get('kind') or 'player',
                'name': row.get('name'),
                'vehicle': row.get('vehicle'),
                'team': row.get('team'),
            })
        return round_id, actors

    def send_pose(self, now=None):
        round_id, actors = self.collect_actors()
        if not actors:
            return False
        try:
            message = build_worker_pose(
                round_id, actors,
                server_hint=now if now is not None else time.time())
        except Exception as exc:
            _log('build_worker_pose failed: %s' % exc)
            return False
        try:
            ok = self.client.send_message(message)
            if not ok:
                _log('worker_pose send failed')
            return bool(ok)
        except Exception as exc:
            _log('worker_pose send error: %s' % exc)
            return False

    # --- Offline battle space (best-effort) ---------------------------------

    def _resolve_map(self, map_name):
        if not map_name:
            return '06_ensk'
        return _MAP_ALIASES.get(map_name, map_name)

    def _enter_offline_space(self, map_name):
        geometry = self._resolve_map(map_name)
        try:
            from gui.mods.offhangar2 import battle
        except Exception as exc:
            _log('offline battle module unavailable: %s' % exc)
            self.space_entered = False
            return False
        try:
            result = battle.enter(geometry)
            self.space_entered = bool(result)
            _log('battle.enter(%r) -> %s' % (geometry, result))
            return self.space_entered
        except Exception as exc:
            _log('battle.enter failed: %s' % exc)
            self.space_entered = False
            return False

    def _leave_offline_space(self):
        try:
            from gui.mods.offhangar2 import battle
            if getattr(battle, 'isInBattle', None) and battle.isInBattle():
                battle.leave()
                _log('battle.leave()')
        except Exception as exc:
            _log('battle.leave skipped: %s' % exc)

    def _sample_local_pose(self):
        """Optional: read avatar position from loaded Offline space."""
        try:
            import BigWorld
            player = BigWorld.player()
            entity = getattr(player, 'vehicle', None) or player
            position = getattr(entity, 'position', None)
            if position is None:
                return None
            yaw = float(getattr(entity, 'yaw', 0.0) or 0.0)
            return ([float(position[0]), float(position[1]), float(position[2])],
                    yaw)
        except Exception:
            return None

    @staticmethod
    def _stable_pos(actor_id, row):
        """Deterministic placeholder position when no worker space sample."""
        base_x = 100.0 if int(row.get('team') or 1) == 1 else -100.0
        jitter = float(int(actor_id) % 9) * 6.0
        return [base_x + jitter, 0.0, float(int(actor_id) % 5) * 4.0]


def install_on_session(session):
    """Attach WorkerAuthority to a ClientSession; returns the authority or None."""
    client = getattr(session, 'client', None)
    if client is None or getattr(client, 'role', 'player') != 'worker':
        return None
    authority = WorkerAuthority(client)
    session.worker_authority = authority
    original_start = session.start

    def _start_and_watch(*args, **kwargs):
        welcome = original_start(*args, **kwargs)
        return welcome

    session.start = _start_and_watch
    _log('worker authority installed for player_id=%s' % getattr(client, 'player_id', None))
    return authority


__all__ = ['WorkerAuthority', 'install_on_session']
