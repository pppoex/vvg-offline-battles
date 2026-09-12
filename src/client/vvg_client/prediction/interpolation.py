# -*- coding: utf-8 -*-
"""Snapshot interpolation buffer placeholder (M6 refines delay / blend).

Keeps a short ring of authority snapshots and can sample remote entity
poses at ``now - delay_ms``. Without two samples it returns the latest row.
"""
from __future__ import absolute_import, division, print_function

from vvg_client.network.connection import monotonic_time


def _row_id(row):
    if isinstance(row, dict):
        return row.get('id')
    return None


def _lerp(a, b, t):
    return float(a) + (float(b) - float(a)) * float(t)


def _mix_pose(row_a, row_b, t):
    """Blend two snapshot pose rows (same entity)."""
    result = {
        'id': _row_id(row_b if row_b is not None else row_a),
        'team': (row_b or row_a or {}).get('team'),
        'name': (row_b or row_a or {}).get('name'),
        'vehicle': (row_b or row_a or {}).get('vehicle'),
    }
    a = row_a or {}
    b = row_b or {}

    def _seq3(key):
        pa = a.get(key)
        pb = b.get(key)
        if not isinstance(pa, (list, tuple)) or not isinstance(pb, (list, tuple)):
            return list(pb if pb is not None else pa or [])
        if len(pa) != 3 or len(pb) != 3:
            return list(pb)
        return [
            _lerp(pa[0], pb[0], t),
            _lerp(pa[1], pb[1], t),
            _lerp(pa[2], pb[2], t),
        ]

    result['pos'] = _seq3('pos')
    for key in ('yaw', 'aim_yaw', 'gun_pitch', 'speed'):
        va = a.get(key)
        vb = b.get(key)
        if va is None and vb is None:
            continue
        if va is None:
            result[key] = float(vb)
        elif vb is None:
            result[key] = float(va)
        else:
            # yaw is periodic: shortest-path blend.
            if key in ('yaw', 'aim_yaw'):
                delta = float(vb) - float(va)
                while delta > 3.141592653589793:
                    delta -= 6.283185307179586
                while delta < -3.141592653589793:
                    delta += 6.283185307179586
                result[key] = float(va) + delta * float(t)
            else:
                result[key] = _lerp(va, vb, t)
    return result


class SnapshotBuffer(object):
    """Ring of snapshot messages ordered by server_tick / wall clock."""

    def __init__(self, max_frames=32):
        self.max_frames = max(2, int(max_frames))
        self._frames = []

    def clear(self):
        self._frames = []

    def push(self, snapshot):
        """Append one snapshot message; keeps newest frames only."""
        if not isinstance(snapshot, dict):
            return
        frame = {
            'snapshot': snapshot,
            'tick': int(snapshot.get('server_tick') or 0),
            'received_at': monotonic_time(),
        }
        self._frames.append(frame)
        if len(self._frames) > self.max_frames:
            del self._frames[0:len(self._frames) - self.max_frames]

    def __len__(self):
        return len(self._frames)

    def latest(self):
        if not self._frames:
            return None
        return self._frames[-1]['snapshot']

    def sample(self, delay_ms=100.0):
        """Return {player_id: pose_row} at (now - delay_ms).

        M4 placeholder: if only one frame exists, return its rows; with two
        or more, blend using wall-clock spacing (assumes even delivery).
        """
        if not self._frames:
            return {}
        if len(self._frames) == 1:
            return self._rows_of(self._frames[0]['snapshot'])

        # Pick the newest pair whose receive times straddle the target time.
        target = monotonic_time() - (float(delay_ms) / 1000.0)
        older = self._frames[-2]
        newer = self._frames[-1]
        for index in range(len(self._frames) - 1):
            left = self._frames[index]
            right = self._frames[index + 1]
            if left['received_at'] <= target <= right['received_at']:
                older = left
                newer = right
                break

        span = newer['received_at'] - older['received_at']
        if span <= 0.0:
            t = 1.0
        else:
            t = (target - older['received_at']) / span
            if t < 0.0:
                t = 0.0
            if t > 1.0:
                t = 1.0

        older_rows = self._rows_by_id(older['snapshot'])
        newer_rows = self._rows_by_id(newer['snapshot'])
        mixed = {}
        for key, row in newer_rows.items():
            mixed[key] = _mix_pose(older_rows.get(key), row, t)
        for key, row in older_rows.items():
            if key not in mixed:
                mixed[key] = row
        return mixed

    @staticmethod
    def _rows_of(snapshot):
        if not isinstance(snapshot, dict):
            return {}
        payload = snapshot.get('payload') or {}
        return SnapshotBuffer._rows_by_id(snapshot)

    @staticmethod
    def _rows_by_id(snapshot):
        if not isinstance(snapshot, dict):
            return {}
        payload = snapshot.get('payload') or {}
        rows = payload.get('players') or ()
        out = {}
        for row in rows:
            if isinstance(row, dict) and row.get('id') is not None:
                out[row['id']] = dict(row)
        return out


__all__ = ['SnapshotBuffer']
