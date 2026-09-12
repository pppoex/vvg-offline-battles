# -*- coding: utf-8 -*-
"""大厅 — 分队与 roster 行构造（纯逻辑，无 IO）。"""
from __future__ import absolute_import, division, print_function

from protocol.constants import MAX_TEAM_SIZE


def team_counts(sessions):
    """统计两队人数。返回 {1: n, 2: m}。"""
    counts = {1: 0, 2: 0}
    for session in sessions:
        team = getattr(session, 'team', None)
        if team in counts:
            counts[team] += 1
    return counts


def assign_team(requested, sessions, team_size=MAX_TEAM_SIZE):
    """选择队伍。

    ``requested`` 为 0/None 表示自动；1 或 2 为指定队（若未满）。
    自动时优先人数较少的一队；平局取 1 队。
    返回 1 或 2。若两队均满则抛 ValueError。
    """
    counts = team_counts(sessions)
    if requested in (1, 2):
        if counts[int(requested)] < int(team_size):
            return int(requested)
        # 指定队已满 → 尝试另一队，再失败则报错
        other = 2 if requested == 1 else 1
        if counts[other] < int(team_size):
            return other
        raise ValueError('both teams are full')

    if counts[1] <= counts[2] and counts[1] < int(team_size):
        return 1
    if counts[2] < int(team_size):
        return 2
    if counts[1] < int(team_size):
        return 1
    raise ValueError('both teams are full')


def spawn_point_for_team(team, map_name=None):
    """按队伍给出出生点占位（M6 再接入真实地图点）。"""
    # 简单对称占位：1 队 -X，2 队 +X
    x = -200.0 if int(team) == 1 else 200.0
    yaw = 0.0 if int(team) == 1 else 3.141592653589793
    return {
        'x': x,
        'y': 0.0,
        'z': 0.0,
        'yaw': yaw,
    }
