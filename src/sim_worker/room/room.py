# -*- coding: utf-8 -*-
"""房间 — 成员、原地 Bot、相位、回合号与轻量快照。"""
from __future__ import absolute_import, division, print_function

import time

from protocol.constants import (
    MAX_TEAM_SIZE,
    PHASE_BATTLE,
    PHASE_WAITING,
)
from protocol.messages import build_battle_live, build_battle_start
from sim_worker.room.lobby import assign_team, spawn_point_for_team, team_counts
from sim_worker.session import BotSlot, PlayerSession, vehicle_data_hash


class Room(object):
    """默认单房间。线程安全由外部（GameServer.lock）保证。"""

    def __init__(self, map_name='vvg_default', team_size=MAX_TEAM_SIZE,
                 stationary_bots=0):
        self.map_name = map_name
        self.team_size = int(team_size)
        self.stationary_bots = int(stationary_bots or 0)
        self.phase = PHASE_WAITING
        self.round_id = 0
        self.state_revision = 0
        self.host_player_id = 0
        self._next_player_id = 1
        self._next_bot_id = 10000
        self._players = {}
        self._order = []
        self._bots = {}
        self._vehicle_hash_group = None

    # --- 成员 ---------------------------------------------------------------

    def player_count(self):
        return len(self._order)

    def players(self):
        return [self._players[pid] for pid in self._order]

    def bots(self):
        return list(self._bots.values())

    def get(self, player_id):
        return self._players.get(player_id)

    def host(self):
        return self._players.get(self.host_player_id)

    def join(self, name, vehicle, capabilities=None, client_build=None,
             requested_team=0, max_health=None, account_key=None, peer=None,
             role='player', vehicle_hash=None, catalog_hash=None):
        """加入大厅。返回 PlayerSession。"""
        session = PlayerSession(
            player_id=self._next_player_id,
            name=name,
            vehicle=vehicle,
            team=1,  # 稍后按 assign_team 重写
            capabilities=capabilities,
            client_build=client_build,
            max_health=max_health,
            account_key=account_key,
            peer=peer,
            role=role,
            vehicle_hash=vehicle_hash,
        )
        # 车数据目录一致性：可选 catalog_hash；不同玩家可开不同车
        group_key = catalog_hash or None
        if role == 'player':
            if not vehicle:
                raise ValueError('player vehicle required')
            if group_key:
                if self._vehicle_hash_group is None:
                    self._vehicle_hash_group = group_key
                elif group_key != self._vehicle_hash_group:
                    raise ValueError(
                        'vehicle_data_mismatch:%s!=%s' % (
                            group_key, self._vehicle_hash_group))
        session.team = assign_team(
            requested_team, self.players(), team_size=self.team_size)
        self._next_player_id += 1
        self._players[session.player_id] = session
        self._order.append(session.player_id)
        self._ensure_host(session)
        self._bump_revision()
        return session

    def _ensure_host(self, joined=None):
        """Host must be a connected player. First valid joiner wins."""
        current = None
        if self.host_player_id:
            current = self._players.get(self.host_player_id)
        if (current is not None
                and getattr(current, 'role', 'player') == 'player'
                and getattr(current, 'connected', False)):
            return
        if (joined is not None
                and getattr(joined, 'role', 'player') == 'player'
                and getattr(joined, 'connected', False)):
            self.host_player_id = joined.player_id
            return
        for player_id in self._order:
            session = self._players.get(player_id)
            if (session is not None
                    and getattr(session, 'role', 'player') == 'player'
                    and getattr(session, 'connected', False)):
                self.host_player_id = player_id
                return
        self.host_player_id = 0

    def leave(self, player_id):
        """移除成员。返回被移除的 session 或 None。"""
        session = self._players.pop(player_id, None)
        if session is None:
            return None
        if player_id in self._order:
            self._order.remove(player_id)
        if self.host_player_id == player_id:
            self.host_player_id = 0
            self._ensure_host()
        if not any(p.role == 'player' for p in self.players()):
            self._vehicle_hash_group = None
        self._bump_revision()
        return session

    def set_team(self, player_id, team):
        """选队。返回 (ok, reason)。"""
        session = self._players.get(player_id)
        if session is None:
            return False, 'unknown_player'
        counts = team_counts(self.players())
        if team not in (1, 2):
            return False, 'invalid_team'
        if session.team == team:
            return True, ''
        if counts[team] >= self.team_size:
            return False, 'team_full'
        session.team = int(team)
        self._bump_revision()
        return True, ''

    def set_vehicle(self, player_id, vehicle, max_health=None):
        session = self._players.get(player_id)
        if session is None:
            return False
        session.vehicle = vehicle
        session.vehicle_hash = vehicle_data_hash(vehicle)
        if max_health is not None:
            session.max_health = max_health
        self._bump_revision()
        return True

    # --- 相位 / 回合 --------------------------------------------------------

    def try_start_battle(self, requester_id, round_seconds=None):
        """host 请求开战。返回 (ok, message_or_reason)。"""
        if self.phase != PHASE_WAITING:
            return False, 'not_waiting'
        if not self._players:
            return False, 'empty_room'
        if requester_id != self.host_player_id:
            return False, 'not_host'
        self.round_id += 1
        self.phase = PHASE_BATTLE
        for session in self.players():
            session.ready = False
            session.ready_round_id = None
            spawn = spawn_point_for_team(session.team, self.map_name)
            session.pose['position'] = [spawn['x'], spawn['y'], spawn['z']]
            session.pose['yaw'] = spawn['yaw']
        self._bots.clear()
        self._spawn_stationary_bots()
        self._bump_revision()
        start = build_battle_start(
            self.round_id, self.map_name, state_revision=self.state_revision)
        live = build_battle_live(
            self.round_id,
            server_tick=0,
            state_revision=self.state_revision,
            server_time_ms=self._now_ms(),
            countdown_seconds=0.0,
            battle_duration_seconds=float(round_seconds or 900),
            timing={'prebattle': 0.0, 'duration': float(round_seconds or 900)},
        )
        return True, {'battle_start': start, 'battle_live': live}

    def _spawn_stationary_bots(self):
        count = max(0, int(self.stationary_bots))
        if count <= 0:
            return
        half = (count + 1) // 2
        for index in range(count):
            team = 1 if index < half else 2
            bot_id = self._next_bot_id
            self._next_bot_id += 1
            spawn = spawn_point_for_team(team, self.map_name)
            # slight lateral offset so bots do not stack
            offset = float(index % 5) * 8.0
            pose = {
                'x': float(spawn['x']) + offset,
                'y': float(spawn['y']),
                'z': float(spawn['z']) + offset * 0.25,
                'yaw': float(spawn['yaw']),
            }
            self._bots[bot_id] = BotSlot(
                bot_id=bot_id,
                name='Bot%02d' % (index + 1),
                vehicle='bot:dummy',
                team=team,
                pose=pose,
            )

    def mark_ready(self, player_id, round_id):
        session = self._players.get(player_id)
        if session is None:
            return False
        if int(round_id) != self.round_id:
            return False
        if self.phase != PHASE_BATTLE:
            return False
        session.ready = True
        session.ready_round_id = self.round_id
        self._bump_revision()
        return True

    def return_to_waiting(self):
        """回合结束后回到大厅。"""
        self.phase = PHASE_WAITING
        self._bots.clear()
        for session in self.players():
            session.ready = False
            session.ready_round_id = None
        self._bump_revision()

    def apply_input(self, player_id, message):
        session = self._players.get(player_id)
        if session is None:
            return False
        if self.phase != PHASE_BATTLE:
            return False
        if message.get('round_id') != self.round_id:
            return False
        session.apply_input(message)
        return True

    def apply_worker_pose(self, round_id, actors):
        """Apply worker pose proposals. Returns number of actors applied."""
        if self.phase != PHASE_BATTLE:
            return 0
        if int(round_id or 0) != self.round_id:
            return 0
        applied = 0
        for actor in actors or ():
            actor_id = actor.get('id')
            session = self._players.get(actor_id)
            if session is not None:
                session.apply_pose(actor)
                applied += 1
                continue
            bot = self._bots.get(actor_id)
            if bot is not None:
                bot.apply_pose(actor)
                applied += 1
        return applied

    def tick_once(self, dt, server_tick):
        """权威在 worker；服务器侧保持输入/提案姿态。"""
        return

    # --- 消息构造 -----------------------------------------------------------

    def roster_players(self):
        rows = [
            s.roster_row() for s in self.players()
            if s.role != 'worker'
        ]
        rows.extend(bot.roster_row() for bot in self.bots())
        return rows

    def snapshot_payload(self):
        rows = [
            s.snapshot_row() for s in self.players()
            if s.role != 'worker'
        ]
        rows.extend(bot.snapshot_row() for bot in self.bots())
        return {'players': rows}

    def welcome_fields(self, session):
        return {
            'map': self.map_name,
            'phase': self.phase,
            'round_id': self.round_id,
            'state_revision': self.state_revision,
            'host_player_id': self.host_player_id,
            'spawn': spawn_point_for_team(session.team, self.map_name),
        }

    def _bump_revision(self):
        self.state_revision += 1

    @staticmethod
    def _now_ms():
        return int(time.time() * 1000)


__all__ = ['Room']
