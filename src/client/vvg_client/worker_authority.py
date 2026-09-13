# -*- coding: utf-8 -*-
"""Worker authority glue for the hidden simulation_worker game process.

0.9.22 model: the worker is NOT a player. It never enters an Offline
single-player match. Shared battle state lives on sim-worker; this process
only publishes authority poses. Visible clients load Offline space for
local rendering only (LAN flags: no Offline private bots).

M6 without Offline space on the worker: poses come from the room roster
(stationary bots + player rows), not from Offline entities.
"""
from __future__ import absolute_import, division, print_function

import sys
import time

from protocol.messages import build_worker_entered, build_worker_pose

LOG_PREFIX = '[VVG worker_auth] '

POSE_HZ = 15.0
# 0.9.22 worker dummy is off-map so it never looks like a player tank.
WORKER_DUMMY_Y = -500.0
_MAP_ALIASES = {
    'vvg_default': '06_ensk',
    'training': '06_ensk',
    'unit_test_map': '06_ensk',
}


def resolve_map_name(map_name):
    if not map_name:
        return '06_ensk'
    return _MAP_ALIASES.get(map_name, map_name)


def _apply_lan_player_flags(prefix):
    """Visible client: Offline must not run a private bot match.

    Shared battle lives on the worker + sim-worker. Player Offline enter is
    only for map/terrain rendering; Offline bots / auto-return would create
    a second independent single-player game.
    """
    try:
        from gui.mods.offhangar2 import config
        config.BOTS_ENABLED = False
        config.BATTLE_AUTO_RETURN = False
        config.BATTLE_RESULTS = False
        sys.stdout.write('%s Offline bots/auto-return/results disabled\n' % prefix)
    except Exception as exc:
        sys.stdout.write('%s lan flags failed: %s\n' % (prefix, exc))
    try:
        from gui.mods.offhangar2 import bots
        original = getattr(bots, 'spawnAll', None)

        def _no_spawn(*args, **kwargs):
            sys.stdout.write('%s bots.spawnAll blocked (LAN)\n' % prefix)
            return []

        if callable(original):
            bots.spawnAll = _no_spawn
            sys.stdout.write('%s patched bots.spawnAll\n' % prefix)
    except Exception as exc:
        sys.stdout.write('%s bots patch failed: %s\n' % (prefix, exc))


def apply_server_pose_to_local(client, session=None):
    """Best-effort: snap local Offline vehicle to server authority pose."""
    try:
        import BigWorld
    except Exception:
        return False
    player = BigWorld.player()
    if player is None:
        return False
    row = None
    if session is not None:
        try:
            row = session.client.snapshot_player_row(session.client.player_id)
        except Exception:
            row = None
    if row is None:
        try:
            row = client.snapshot_player_row(client.player_id)
        except Exception:
            return False
    if not isinstance(row, dict):
        return False
    pos = row.get('pos')
    if not isinstance(pos, (list, tuple)) or len(pos) != 3:
        return False
    try:
        target = getattr(player, 'vehicle', None) or player
        target.position = (float(pos[0]), float(pos[1]), float(pos[2]))
        if row.get('yaw') is not None and hasattr(target, 'yaw'):
            target.yaw = float(row['yaw'])
        return True
    except Exception as exc:
        sys.stdout.write('[VVG player] apply pose failed: %s\n' % exc)
        return False


def enter_offline_space(map_name, log_prefix=None, lan_player=False,
                       worker_observe=False, authority=False):
    """Enter Offline battle space.

    lan_player=True: visible client map/terrain only — no Offline private bots.
    authority=True: hidden worker enters Offline as the battle authority
    (still not a room player). Offline private bots stay off so this is not
    a second independent Offline bot match.
    worker_observe=True: legacy alias for authority.
    """
    prefix = log_prefix or LOG_PREFIX
    authority = bool(authority or worker_observe)
    if not lan_player and not authority:
        sys.stdout.write(
            '%s refusing Offline enter for non-player (use authority flag)\n'
            % prefix)
        return False
    geometry = resolve_map_name(map_name)
    try:
        from gui.mods.offhangar2 import battle
    except Exception as exc:
        sys.stdout.write('%s battle module unavailable: %s\n' % (prefix, exc))
        return False
    _apply_lan_player_flags(prefix)
    try:
        already = False
        if getattr(battle, 'isInBattle', None):
            already = bool(battle.isInBattle())
        if already:
            sys.stdout.write('%s already in battle; skip enter\n' % prefix)
            return True
        result = battle.enter(geometry)
        sys.stdout.write('%s battle.enter(%r) authority=%s lan_player=%s -> %s\n' % (
            prefix, geometry, bool(authority), bool(lan_player), result))
        if authority and result:
            _move_worker_dummy_offmap(prefix)
        return bool(result)
    except Exception as exc:
        sys.stdout.write('%s battle.enter failed: %s\n' % (prefix, exc))
        return False


def _move_worker_dummy_offmap(prefix):
    """Put the worker's local avatar off-map (0.9.22 WORKER_DUMMY_Y)."""
    try:
        import BigWorld
    except Exception:
        return False
    try:
        player = BigWorld.player()
        if player is None:
            return False
        target = getattr(player, 'vehicle', None) or player
        target.position = (0.0, float(WORKER_DUMMY_Y), 0.0)
        sys.stdout.write(
            '%s worker dummy at y=%s (not a room player)\n'
            % (prefix, WORKER_DUMMY_Y))
        return True
    except Exception as exc:
        sys.stdout.write('%s worker dummy move failed: %s\n' % (prefix, exc))
        return False


def leave_offline_space(log_prefix=None):
    prefix = log_prefix or LOG_PREFIX
    try:
        from gui.mods.offhangar2 import battle
        if getattr(battle, 'isInBattle', None) and battle.isInBattle():
            battle.leave()
            sys.stdout.write('%s battle.leave()\n' % prefix)
            return True
    except Exception as exc:
        sys.stdout.write('%s battle.leave skipped: %s\n' % (prefix, exc))
    return False


def _log(message):
    try:
        sys.stdout.write(LOG_PREFIX + str(message) + '\n')
        sys.stdout.flush()
    except Exception:
        pass


class WorkerAuthority(object):
    """Publish room authority poses. Never enters Offline as a player."""

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
        _log('battle_start round=%s map=%s (authority enter)' % (
            round_id, map_name))
        self._last_round = round_id
        self.in_battle = True
        # 0.9.22: worker is authority in a native battle space, not a room
        # player. Offline private bots stay off; sim-worker roster + poses
        # carry the shared battle.
        self.space_entered = enter_offline_space(
            map_name,
            log_prefix=LOG_PREFIX,
            authority=True,
        )
        _log('authority space_entered=%s' % bool(self.space_entered))
        try:
            self.client.send_message(
                build_worker_entered(round_id, map_name=map_name))
            _log('sent worker_entered round=%s' % round_id)
        except Exception as exc:
            _log('send worker_entered failed: %s' % exc)

    def on_battle_live(self, message):
        if not self.in_battle:
            self.on_battle_start(message)

    def on_leave_or_waiting(self):
        if self.in_battle:
            _log('leave battle authority')
        self.in_battle = False
        if self.space_entered:
            leave_offline_space(log_prefix=LOG_PREFIX)
        self.space_entered = False

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
        """Build worker_pose actor list from room roster + local samples."""
        client = self.client
        round_id = int(getattr(client, 'round_id', 0) or 0)
        actors = []
        roster = getattr(client, 'roster', None)
        rows = []
        if isinstance(roster, dict):
            rows = list(roster.get('players') or ())
        local_sample = self._sample_local_pose()
        for row in rows:
            actor_id = row.get('player_id') or row.get('id')
            if actor_id is None:
                continue
            # Worker dummy is not in roster. Use local pose for own id only.
            if local_sample is not None and actor_id == getattr(client, 'player_id', None):
                pos, yaw = local_sample
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

    def _sample_local_pose(self):
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

    def _stable_pos(self, actor_id, row):
        """Deterministic placeholder position for roster rows."""
        team = int(row.get('team') or 1)
        base_x = 100.0 if team == 1 else -100.0
        jitter = float(int(actor_id) % 9) * 6.0
        return [base_x + jitter, 0.0, float(int(actor_id) % 5) * 4.0]


def install_on_session(session):
    """Attach WorkerAuthority to a ClientSession; returns the authority or None."""
    client = getattr(session, 'client', None)
    if client is None or getattr(client, 'role', 'player') != 'worker':
        return None
    authority = WorkerAuthority(client)
    session.worker_authority = authority
    _log('worker authority installed (no Offline player enter)')
    return authority


__all__ = [
    'WorkerAuthority',
    'install_on_session',
    'enter_offline_space',
    'leave_offline_space',
    'resolve_map_name',
    'apply_server_pose_to_local',
]
