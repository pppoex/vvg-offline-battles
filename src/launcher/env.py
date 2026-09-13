# -*- coding: utf-8 -*-
"""Build the VVG_* environment for sim-worker and game clients."""
from __future__ import absolute_import, division, print_function

import os

DEFAULT_SERVER_HOST = '127.0.0.1'
DEFAULT_SERVER_PORT = 28782
DEFAULT_PLAYER_NAME = 'Player'
DEFAULT_PLAYER_VEHICLE = 'ussr:R05_LT'
MODE_PLAYER = 'player'
MODE_WORKER = 'simulation_worker'


def base_env(overlay=None):
    """Return a copy of os.environ optionally overlaid with *overlay*."""
    env = os.environ.copy()
    if overlay:
        env.update({str(k): str(v) for k, v in overlay.items()})
    return env


def client_env(mode, name=None, vehicle=None, host=None, port=None):
    """Environment for a game client process (player or simulation_worker).

    Only sets VVG_* keys the thin client actually reads (see bootstrap).
    """
    if mode not in (MODE_PLAYER, MODE_WORKER):
        raise ValueError('invalid client mode: %r' % (mode,))
    host = host or DEFAULT_SERVER_HOST
    port = int(port if port is not None else DEFAULT_SERVER_PORT)
    env = {
        'VVG_SERVER_HOST': str(host),
        'VVG_SERVER_PORT': str(port),
        'VVG_CLIENT_MODE': mode,
        'VVG_ALLOW_MULTIPLE_CLIENTS': '1',
    }
    if mode == MODE_PLAYER:
        env['VVG_PLAYER_NAME'] = name or DEFAULT_PLAYER_NAME
        env['VVG_PLAYER_VEHICLE'] = vehicle or DEFAULT_PLAYER_VEHICLE
    else:
        # Keep identity vars present for diagnostics; client forces worker role.
        if name:
            env['VVG_PLAYER_NAME'] = name
        env.setdefault('VVG_PLAYER_NAME', 'worker')
    return env


def server_env(host=None, port=None, pythonpath=None):
    """Environment for a sim-worker process."""
    host = host or DEFAULT_SERVER_HOST
    port = int(port if port is not None else DEFAULT_SERVER_PORT)
    env = {
        'VVG_SERVER_HOST': str(host),
        'VVG_SERVER_PORT': str(port),
        'PYTHONPATH': pythonpath or os.environ.get('PYTHONPATH', ''),
    }
    return env
