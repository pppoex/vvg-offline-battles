# -*- coding: utf-8 -*-
"""ClientSession — BattleClient + LocalPlayer + SnapshotBuffer glue.

One session owns network + prediction state. ``tick(dt)`` is the single
update entry used by BigWorld callbacks and by integration tests.
"""
from __future__ import absolute_import, division, print_function

from vvg_client.network.client import BattleClient
from vvg_client.network.reconnect import ReconnectPolicy
from vvg_client.prediction.interpolation import SnapshotBuffer
from vvg_client.prediction.local_player import LocalPlayer


class ClientSession(object):
    """High-level thin-client session.

    Parameters mirror ``BattleClient``; defaults read ``sdk.config``.
    """

    def __init__(self, name, vehicle, host=None, port=None,
                 capabilities=None, client_build=None,
                 reconnect_policy=None, interp_delay_ms=None):
        self.client = BattleClient(
            name=name,
            vehicle=vehicle,
            host=host,
            port=port,
            capabilities=capabilities,
            client_build=client_build,
        )
        self.local_player = LocalPlayer()
        self.snapshots = SnapshotBuffer()
        self.reconnect = (
            reconnect_policy if reconnect_policy is not None
            else ReconnectPolicy.from_config())
        self.interp_delay_ms = self._default_interp_delay(interp_delay_ms)
        self.connected_once = False
        self.last_tick_wall = None

    @staticmethod
    def _default_interp_delay(explicit):
        if explicit is not None:
            return float(explicit)
        try:
            from sdk import config
            return float(config._get('INTERP_BUFFER_MS', config.INTERP_BUFFER_MS))
        except Exception:
            return 100.0

    # --- 生命周期 -----------------------------------------------------------

    @property
    def player_id(self):
        return self.client.player_id

    @property
    def connected(self):
        return self.client.connected

    @property
    def welcome(self):
        return self.client.welcome

    @property
    def last_error(self):
        return self.client.last_error

    def start(self, timeout=5.0):
        """Connect + handshake + seed local player from spawn."""
        welcome = self.client.connect_and_handshake(timeout=timeout)
        if welcome is None:
            return None
        self.connected_once = True
        self.reconnect.reset()
        self.local_player.player_id = self.client.player_id
        if self.client.spawn:
            self.local_player.apply_spawn(self.client.spawn)
        return welcome

    def stop(self, polite=True):
        self.client.disconnect(polite=polite)

    # --- 每帧 ---------------------------------------------------------------

    def tick(self, dt=None, forward=0.0, turn=0.0, aim_yaw=None,
             gun_pitch=None, send_input=False):
        """Pump network, step local prediction, absorb authority rows.

        Returns a small status dict for logs / tests.
        """
        received = self.client.pump()
        absorbed = self._absorb_authority()

        if dt is None:
            now = self._now()
            if self.last_tick_wall is None:
                dt = 0.0
            else:
                dt = max(0.0, now - self.last_tick_wall)
            self.last_tick_wall = now
        else:
            dt = max(0.0, float(dt))

        self.local_player.set_input(
            forward=forward, turn=turn,
            aim_yaw=aim_yaw, gun_pitch=gun_pitch)
        # Hard-correct frame: keep authority pose, do not re-mark as predicted.
        if self.client.connected and not absorbed:
            self.local_player.step(dt)

        if send_input and self.client.connected and self.client.round_id:
            pose = self.local_player.pose()
            self.client.send_input(
                forward=self.local_player.forward,
                turn=self.local_player.turn,
                aim_yaw=self.local_player.aim_yaw,
                gun_pitch=self.local_player.gun_pitch,
                position=pose['position'],
                yaw=pose['yaw'],
                speed=pose['speed'],
            )

        return {
            'received': received,
            'connected': self.client.connected,
            'phase': self.client.phase,
            'round_id': self.client.round_id,
            'pose': self.local_player.pose(),
        }

    def _absorb_authority(self):
        """Push new snapshot into buffer / local player. True if corrected."""
        snapshot = self.client.last_snapshot
        if snapshot is None:
            return False
        # Only feed new frames into the buffer / correction path.
        tick = int(snapshot.get('server_tick') or 0)
        if getattr(self, '_last_absorbed_tick', None) == tick:
            return False
        self._last_absorbed_tick = tick
        self.snapshots.push(snapshot)
        row = self.client.snapshot_player_row(self.client.player_id)
        if row is not None:
            self.local_player.on_authority_row(
                row, server_time_ms=snapshot.get('server_time_ms'))
            return True
        return False

    def remote_poses(self):
        """Interpolated remote rows (id -> pose) for renderers."""
        return self.snapshots.sample(delay_ms=self.interp_delay_ms)

    def is_host(self):
        return self.client.is_host()

    @staticmethod
    def _now():
        from vvg_client.network.connection import monotonic_time
        return monotonic_time()


__all__ = ['ClientSession']
