# -*- coding: utf-8 -*-
"""世界 tick 循环 — 固定 30 Hz 步进，快照按倍频触发。

参考 lan_battle_server 的调度：落后时连续消费欠账 tick，而不是重置相位。
"""
from __future__ import absolute_import, division, print_function

import time


class TickLoop(object):
    """驱动 ``world.tick_once(dt)`` 与可选快照回调的循环。

    参数：
      world — 需要有 ``running`` 布尔与 ``tick_once(dt, server_tick)``；
              可选 ``should_snapshot(server_tick)`` / ``broadcast_snapshot(server_tick)``。
      tick_hz — 世界步进频率（默认 30）。
      snapshot_hz — 快照频率；None 表示由 world.should_snapshot 决定。
    """

    def __init__(self, world, tick_hz=30.0, snapshot_hz=None,
                 clock=None, sleeper=None, max_consecutive_failures=2):
        if tick_hz <= 0:
            raise ValueError('tick_hz must be positive')
        self.world = world
        self.tick_hz = float(tick_hz)
        self.interval = 1.0 / self.tick_hz
        self.snapshot_ticks = None
        if snapshot_hz:
            if snapshot_hz <= 0:
                raise ValueError('snapshot_hz must be positive')
            self.snapshot_ticks = max(
                1, int(round(self.tick_hz / float(snapshot_hz))))
        self._clock = clock if clock is not None else time.perf_counter
        self._sleeper = sleeper if sleeper is not None else time.sleep
        self.max_consecutive_failures = int(max_consecutive_failures)
        self.server_tick = 0
        self.consecutive_failures = 0

    def run(self, shutdown_callback=None):
        """阻塞运行直到 world.running 为假。"""
        next_tick = self._clock() + self.interval
        try:
            while getattr(self.world, 'running', True):
                now = self._clock()
                delay = next_tick - now
                if delay > 0.0:
                    self._sleeper(delay)
                    continue
                while (getattr(self.world, 'running', True)
                       and now + 1e-9 >= next_tick):
                    self._step_once(shutdown_callback)
                    if not getattr(self.world, 'running', True):
                        return
                    next_tick += self.interval
                    now = self._clock()
        except Exception:
            self._halt(shutdown_callback)
            raise

    def _step_once(self, shutdown_callback):
        try:
            self.world.tick_once(self.interval, self.server_tick)
            self.server_tick += 1
            if self._snapshot_due(self.server_tick):
                broadcaster = getattr(self.world, 'broadcast_snapshot', None)
                if callable(broadcaster):
                    broadcaster(self.server_tick)
        except Exception:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.max_consecutive_failures:
                self._halt(shutdown_callback)
                raise
        else:
            self.consecutive_failures = 0

    def _snapshot_due(self, server_tick):
        if self.snapshot_ticks is not None:
            return server_tick > 0 and server_tick % self.snapshot_ticks == 0
        should = getattr(self.world, 'should_snapshot', None)
        if callable(should):
            return bool(should(server_tick))
        return False

    def _halt(self, shutdown_callback):
        self.world.running = False
        if shutdown_callback is not None:
            try:
                shutdown_callback()
            except Exception:
                pass


def snapshot_interval_ticks(tick_hz, snapshot_hz):
    """快照间隔 tick 数（≥1）。"""
    if tick_hz <= 0 or snapshot_hz <= 0:
        raise ValueError('hz must be positive')
    return max(1, int(round(float(tick_hz) / float(snapshot_hz))))


__all__ = ['TickLoop', 'snapshot_interval_ticks']
