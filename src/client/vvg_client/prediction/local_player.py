# -*- coding: utf-8 -*-
"""Local player prediction placeholder (M6 will replace with real integration).

M4 behaviour:
- Seed pose from welcome.spawn (or origin).
- Dead-reckon with the same clamped input envelope the wire uses.
- Hard-authority correct on the local player's snapshot row.
"""
from __future__ import absolute_import, division, print_function

import math

# Match protocol.constants bounds used on the wire.
_MAX_GUN_PITCH = 1.2
_MAX_ATTITUDE = 0.61
_MAX_SPEED = 200.0


def _clamp(value, low, high):
    value = float(value)
    if value < low:
        return low
    if value > high:
        return high
    return value


def _wrap_angle(angle):
    angle = float(angle) % (2.0 * math.pi)
    if angle > math.pi:
        angle -= 2.0 * math.pi
    return angle


class LocalPlayer(object):
    """Authoritative-local pose cache + simple kinematic step."""

    def __init__(self, player_id=None, spawn=None):
        self.player_id = player_id
        self.position = [0.0, 0.0, 0.0]
        self.yaw = 0.0
        self.aim_yaw = 0.0
        self.gun_pitch = 0.0
        self.speed = 0.0
        self.forward = 0.0
        self.turn = 0.0
        self.authority_time = None
        self.predicted = False
        if spawn:
            self.apply_spawn(spawn)

    def apply_spawn(self, spawn):
        if not isinstance(spawn, dict):
            return
        try:
            self.position = [
                float(spawn.get('x', 0.0)),
                float(spawn.get('y', 0.0)),
                float(spawn.get('z', 0.0)),
            ]
            self.yaw = float(spawn.get('yaw', 0.0))
        except (TypeError, ValueError):
            return
        self.aim_yaw = self.yaw
        self.gun_pitch = 0.0
        self.speed = 0.0

    def set_input(self, forward=0.0, turn=0.0, aim_yaw=None, gun_pitch=None):
        self.forward = _clamp(forward, -1.0, 1.0)
        self.turn = _clamp(turn, -1.0, 1.0)
        if aim_yaw is not None:
            self.aim_yaw = float(aim_yaw)
        if gun_pitch is not None:
            self.gun_pitch = _clamp(gun_pitch, -_MAX_GUN_PITCH, _MAX_GUN_PITCH)

    def step(self, dt):
        """Advance local pose. Turn rate / speed are placeholders (M6)."""
        dt = max(0.0, float(dt))
        if dt == 0.0:
            return
        # Placeholder kinematics: turn ~ 1.2 rad/s at full stick, speed ~ 10 m/s.
        turn_rate = 1.2 * self.turn
        self.yaw = _wrap_angle(self.yaw + turn_rate * dt)
        self.aim_yaw = _wrap_angle(self.aim_yaw + turn_rate * dt)
        cruise = 10.0 * abs(self.forward)
        target_speed = cruise if self.forward >= 0.0 else -cruise * 0.4
        # Light smoothing toward target speed.
        self.speed = self.speed + (target_speed - self.speed) * min(1.0, dt * 4.0)
        self.speed = _clamp(self.speed, -_MAX_SPEED, _MAX_SPEED)
        # BigWorld: yaw=0 faces +Z; right-handed Y-up.
        dx = math.sin(self.yaw) * self.speed * dt
        dz = math.cos(self.yaw) * self.speed * dt
        self.position[0] += dx
        self.position[2] += dz
        self.predicted = True

    def on_authority_row(self, row, server_time_ms=None):
        """Hard-correct from the local player's snapshot pose row."""
        if not isinstance(row, dict):
            return
        pos = row.get('pos')
        if isinstance(pos, (list, tuple)) and len(pos) == 3:
            try:
                self.position = [float(pos[0]), float(pos[1]), float(pos[2])]
            except (TypeError, ValueError):
                pass
        for key, attr in (
                ('yaw', 'yaw'),
                ('aim_yaw', 'aim_yaw'),
                ('gun_pitch', 'gun_pitch'),
                ('speed', 'speed')):
            if row.get(key) is None:
                continue
            try:
                setattr(self, attr, float(row[key]))
            except (TypeError, ValueError):
                pass
        self.gun_pitch = _clamp(self.gun_pitch, -_MAX_GUN_PITCH, _MAX_GUN_PITCH)
        self.speed = _clamp(self.speed, -_MAX_SPEED, _MAX_SPEED)
        self.authority_time = server_time_ms
        self.predicted = False

    def pose(self):
        return {
            'position': [
                float(self.position[0]),
                float(self.position[1]),
                float(self.position[2]),
            ],
            'yaw': float(self.yaw),
            'aim_yaw': float(self.aim_yaw),
            'gun_pitch': float(self.gun_pitch),
            'speed': float(self.speed),
            'predicted': bool(self.predicted),
        }


__all__ = ['LocalPlayer']
