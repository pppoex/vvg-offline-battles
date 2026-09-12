# -*- coding: utf-8 -*-
"""房间 — 成员、相位、回合号与轻量快照。"""
from __future__ import absolute_import, division, print_function

import time

from protocol.constants import (
    MAX_TEAM_SIZE,
    PHASE_BATTLE,
    PHASE_WAITING,
)
from protocol.messages import build_battle_live, build_battle_start
from sim_worker.room.lobby import assign_team, spawn_point_for_team, team_counts
from sim_worker.session import PlayerSession


class Room(object):
    """默认单房间。线程安全由外部（GameServer.lock）保证。"""

    def __init__(self, map_name='vvg_default', team_size=MAX_TEAM_SIZE):
        self.map_name = map_name
        self.team_size = int(team_size)
        self.phase = PHASE_WAITING
        self.round_id = 0
        self.state_revision = 0
        self.host_player_id = 0
        self._next_player_id = 1
        self._players = {}
        self._order = []

    # --- 成员 ---------------------------------------------------------------

    def player_count(self):
        return len(self._order)

    def players(self):
        return [self._players[pid] for pid in self._order]

    def get(self, player_id):
        return self._players.get(player_id)

    def host(self):
        return self._players.get(self.host_player_id)

    def join(self, name, vehicle, capabilities=None, client_build=None,
             requested_team=0, max_health=None, account_key=None, peer=None):
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
        )
        session.team = assign_team(
            requested_team, self.players(), team_size=self.team_size)
        self._next_player_id += 1
        self._players[session.player_id] = session
        self._order.append(session.player_id)
        if self.host_player_id == 0:
            self.host_player_id = session.player_id
        self._bump_revision()
        return session

    def leave(self, player_id):
        """移除成员。返回被移除的 session 或 None。"""
        session = self._players.pop(player_id, None)
        if session is None:
            return None
        if player_id in self._order:
            self._order.remove(player_id)
        if self.host_player_id == player_id:
            self.host_player_id = self._order[0] if self._order else 0
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
        """回合结束后回到大厅（M3：手动 leave_battle 或超时时调用）。"""
        self.phase = PHASE_WAITING
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

    def tick_once(self, dt, server_tick):
        """权威占位：M3 仅保留输入姿态；M6 接入运动积分。"""
        return

    # --- 消息构造 -----------------------------------------------------------

    def roster_players(self):
        return [s.roster_row() for s in self.players()]

    def snapshot_payload(self):
        return {
            'players': [s.snapshot_row() for s in self.players()],
        }

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


__all__ = ['Room', 'ProtocolError']
