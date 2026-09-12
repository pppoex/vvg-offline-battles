# -*- coding: utf-8 -*-
"""Reconnect policy — exponential backoff from ``sdk.config`` defaults.

M4 only provides the policy helper; automatic reconnect is wired in M8.
"""
from __future__ import absolute_import, division, print_function


def _load_config():
    try:
        from sdk import config
        return config
    except ImportError:
        return None


class ReconnectPolicy(object):
    """Attempt counter + delay schedule. Thread-unsafe by design (owner uses)."""

    def __init__(self, enabled=True, max_attempts=10, initial_delay=0.5,
                 backoff=2.0, max_delay=8.0):
        self.enabled = bool(enabled)
        self.max_attempts = int(max_attempts)
        self.initial_delay = float(initial_delay)
        self.backoff = float(backoff)
        self.max_delay = float(max_delay)
        self._attempt = 0

    @classmethod
    def from_config(cls, config=None):
        if config is None:
            config = _load_config()
        if config is None or not hasattr(config, 'get_reconnect_policy'):
            return cls()
        policy = config.get_reconnect_policy()
        return cls(
            enabled=policy.get('enabled', True),
            max_attempts=policy.get('max_attempts', 10),
            initial_delay=policy.get('initial_delay', 0.5),
            backoff=policy.get('backoff', 2.0),
            max_delay=policy.get('max_delay', 8.0),
        )

    @property
    def attempt(self):
        return self._attempt

    def reset(self):
        self._attempt = 0

    def next_delay(self):
        """Seconds to wait before the next attempt; None when exhausted."""
        if not self.enabled:
            return None
        if self._attempt >= self.max_attempts:
            return None
        delay = self.initial_delay * (self.backoff ** self._attempt)
        if delay > self.max_delay:
            delay = self.max_delay
        self._attempt += 1
        return delay

    def can_retry(self):
        if not self.enabled:
            return False
        return self._attempt < self.max_attempts


__all__ = ['ReconnectPolicy']
