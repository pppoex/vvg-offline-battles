# -*- coding: utf-8 -*-
"""Remote vehicle scene driven by interpolated snapshot poses.

M6 delivers a testable pure-Python entity registry. Inside BigWorld, each
entity's ``position`` / ``yaw`` is written when writable (best-effort; a full
0.9.22 compound-model port is deferred). Outside the game, the registry still
tracks poses so integration tests can assert sync.
"""
from __future__ import absolute_import, division, print_function

import sys

LOG_PREFIX = '[VVG remote_scene] '
_REPORTED_MISSING_GATE = False


def _log(message):
    try:
        sys.stdout.write(LOG_PREFIX + str(message) + '\n')
        sys.stdout.flush()
    except Exception:
        pass


def _entity_id(row):
    if not isinstance(row, dict):
        return None
    return row.get('id')


class RemoteEntity(object):
    """One remote vehicle/bot slot with last applied pose."""

    def __init__(self, entity_id, meta=None):
        self.entity_id = entity_id
        self.meta = dict(meta or {})
        self.position = [0.0, 0.0, 0.0]
        self.yaw = 0.0
        self.aim_yaw = 0.0
        self.gun_pitch = 0.0
        self.speed = 0.0
        self.vehicle = self.meta.get('vehicle')
        self.team = self.meta.get('team')
        self.name = self.meta.get('name')
        self.kind = self.meta.get('kind') or 'player'
        self.bw_entity = None
        self.updates = 0

    def apply_pose(self, row):
        if not isinstance(row, dict):
            return False
        position = row.get('pos')
        if isinstance(position, (list, tuple)) and len(position) == 3:
            self.position = [
                float(position[0]),
                float(position[1]),
                float(position[2]),
            ]
        if row.get('yaw') is not None:
            self.yaw = float(row['yaw'])
        if row.get('aim_yaw') is not None:
            self.aim_yaw = float(row['aim_yaw'])
        if row.get('gun_pitch') is not None:
            self.gun_pitch = float(row['gun_pitch'])
        if row.get('speed') is not None:
            self.speed = float(row['speed'])
        for key in ('name', 'vehicle', 'team', 'kind'):
            if row.get(key) is not None:
                setattr(self, key, row[key])
        self.updates += 1
        return True

    def to_dict(self):
        return {
            'id': self.entity_id,
            'name': self.name,
            'vehicle': self.vehicle,
            'team': self.team,
            'kind': self.kind,
            'pos': list(self.position),
            'yaw': self.yaw,
            'aim_yaw': self.aim_yaw,
            'gun_pitch': self.gun_pitch,
            'speed': self.speed,
            'updates': self.updates,
        }


class RemoteScene(object):
    """Registry of remote entities + optional BigWorld pose writes."""

    def __init__(self, local_player_id=None):
        self.local_player_id = local_player_id
        self._entities = {}
        self.active = False
        self.applied_frames = 0
        self.dropped_local = 0

    def clear(self):
        self._entities = {}
        self.active = False
        self.applied_frames = 0
        self.dropped_local = 0

    def entities(self):
        return list(self._entities.values())

    def get(self, entity_id):
        return self._entities.get(entity_id)

    def apply_sample(self, poses_by_id):
        """Apply one interpolated {id: row} map. Returns entity count."""
        if not isinstance(poses_by_id, dict):
            return 0
        self.active = True
        touched = set()
        for key, row in poses_by_id.items():
            entity_id = row.get('id') if isinstance(row, dict) else key
            if entity_id is None:
                entity_id = key
            try:
                entity_id = int(entity_id)
            except (TypeError, ValueError):
                continue
            if (self.local_player_id is not None
                    and entity_id == self.local_player_id):
                self.dropped_local += 1
                continue
            entity = self._entities.get(entity_id)
            if entity is None:
                entity = RemoteEntity(entity_id)
                self._entities[entity_id] = entity
                _log('spawn remote id=%s kind=%s' % (
                    entity_id, (row or {}).get('kind')))
            entity.apply_pose(row)
            self._try_write_bigworld(entity)
            touched.add(entity_id)
        for stale in list(self._entities.keys()):
            if stale not in touched:
                # keep last pose; do not despawn mid-fight on one missing frame
                pass
        self.applied_frames += 1
        return len(self._entities)

    def _try_write_bigworld(self, entity):
        """Best-effort native pose write; silent outside BigWorld."""
        global _REPORTED_MISSING_GATE
        try:
            import BigWorld
        except Exception:
            return False
        bw_entity = entity.bw_entity
        if bw_entity is None:
            return False
        try:
            position = getattr(bw_entity, 'position', None)
            if position is not None:
                bw_entity.position = (
                    entity.position[0],
                    entity.position[1],
                    entity.position[2],
                )
            if hasattr(bw_entity, 'yaw'):
                bw_entity.yaw = entity.yaw
            return True
        except Exception:
            if not _REPORTED_MISSING_GATE:
                _REPORTED_MISSING_GATE = True
                _log('BigWorld pose write unavailable; registry-only mode')
            return False

    def bind_bigworld_entity(self, entity_id, bw_entity):
        entity = self._entities.get(entity_id)
        if entity is None:
            entity = RemoteEntity(entity_id)
            self._entities[entity_id] = entity
        entity.bw_entity = bw_entity
        return entity


__all__ = ['RemoteScene', 'RemoteEntity']
