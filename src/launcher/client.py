# -*- coding: utf-8 -*-
"""Launch player / worker game clients via vvg_worker_starter.exe."""
from __future__ import absolute_import, division, print_function

import os
import subprocess

from launcher import env as envmod
from launcher import paths as pathmod
from launcher import ports


def find_fallback_game_exe(root):
    """Path to WorldOfTanks.exe under win64/ (direct launch without starter)."""
    return os.path.join(pathmod.game_root(root), 'win64', 'WorldOfTanks.exe')


def build_starter_argv(starter, role, show=None):
    """argv for vvg_worker_starter.exe.

    role: 'player' | 'worker'
    show: None (starter default), True (--show), False (--hide)
    """
    argv = [starter]
    if role == 'player':
        argv.append('--player')
    else:
        argv.append('--worker-only')
    if show is True:
        argv.append('--show')
    elif show is False:
        argv.append('--hide')
    return argv


def build_fallback_argv(role, show=None, root=None):
    """Direct WorldOfTanks.exe launch (no multi-instance guard injection)."""
    del show  # no window control without the starter
    return [find_fallback_game_exe(root)]


def resolve_launcher_argv(role, show=None, root=None, starter=None,
                          force_fallback=False):
    """Pick starter vs direct exe. Returns (argv, kind, path)."""
    game_root = pathmod.game_root(root)
    starter = starter or pathmod.starter_exe(game_root)
    if not force_fallback and os.path.isfile(starter):
        return build_starter_argv(starter, role, show=show), 'starter', starter
    exe = find_fallback_game_exe(game_root)
    if not os.path.isfile(exe):
        raise SystemExit(
            'no client launcher found:\n'
            '  starter: %s (missing)\n'
            '  game:    %s (missing)\n'
            'run `python -m launcher deploy` first, or pass --game-root'
            % (starter, exe))
    return build_fallback_argv(role, show=show, root=game_root), 'game-exe', exe


def start_client(role, name=None, vehicle=None, host=None, port=None,
                 show=None, root=None, workspace=None, force_fallback=False,
                 log=None):
    """Spawn a player or worker client. Returns (proc, kind, path).

    Does not wait for hangar / join — the game process runs independently.
    """
    log = log or ports.log
    if role == 'player':
        mode = envmod.MODE_PLAYER
    elif role == 'worker':
        mode = envmod.MODE_WORKER
    else:
        raise ValueError('role must be player or worker, got %r' % (role,))

    host = host or envmod.DEFAULT_SERVER_HOST
    port = int(port if port is not None else envmod.DEFAULT_SERVER_PORT)

    argv, kind, path = resolve_launcher_argv(
        role, show=show, root=root, force_fallback=force_fallback)
    overlay = envmod.client_env(
        mode, name=name, vehicle=vehicle, host=host, port=port)
    child_env = envmod.base_env(overlay)

    log('starting %s client (%s): %s' % (role, kind, path))
    log('env: VVG_CLIENT_MODE=%s VVG_SERVER_HOST=%s VVG_SERVER_PORT=%s'
        % (mode, host, port))
    if mode == envmod.MODE_PLAYER:
        log('env: VVG_PLAYER_NAME=%s VVG_PLAYER_VEHICLE=%s'
            % (overlay['VVG_PLAYER_NAME'], overlay['VVG_PLAYER_VEHICLE']))

    cwd = os.path.dirname(path) if kind == 'starter' else pathmod.game_root(root)
    proc = subprocess.Popen(argv, env=child_env, cwd=cwd)
    log('%s client pid=%s' % (role, proc.pid))
    if mode == envmod.MODE_PLAYER:
        log('ensure sim-worker is running on %s:%s before the client joins'
            % (host, port))
    return proc, kind, path
