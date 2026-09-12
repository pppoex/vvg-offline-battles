# -*- coding: utf-8 -*-
"""Mod bootstrap — ensure paths, optionally install BigWorld hooks.

Called from ``mod_vvg_client.init()``. Safe to call twice (idempotent).
Never raises: game.init must survive any thin-client failure.
"""
from __future__ import absolute_import, division, print_function

import os
import sys

LOG_PREFIX = '[VVG thin client] '

_started = False
_session = False  # sentinel replaced by object / None after start
_session = None


def _log(message):
    try:
        text = LOG_PREFIX + str(message)
        sys.stdout.write(text + '\n')
        sys.stdout.flush()
    except Exception:
        pass


def _has_pkg(directory, name):
    return os.path.isdir(os.path.join(directory, name))


def _res_mods_alternates(directory):
    """Yield res_mods-style mods dirs when a junction omits res_mods.

    Some installs expose both ``<root>/scripts/...`` and
    ``<root>/res_mods/<ver>/scripts/...``. If this file was imported via the
    junction view, packages live only under res_mods.
    """
    if not directory:
        return
    norm = os.path.normpath(directory)
    parts = norm.split(os.sep)
    # Find trailing ...\scripts\client\gui\mods
    tail = ['scripts', 'client', 'gui', 'mods']
    if [p.lower() for p in parts[-4:]] != tail:
        return
    root = os.sep.join(parts[:-4])
    res_mods = os.path.join(root, 'res_mods')
    if not os.path.isdir(res_mods):
        return
    try:
        versions = sorted(os.listdir(res_mods), reverse=True)
    except Exception:
        return
    for name in versions:
        yield os.path.join(res_mods, name, 'scripts', 'client', 'gui', 'mods')


def _candidate_mod_dirs():
    """Parent dirs of this package that may hold protocol/sdk as siblings."""
    here = os.path.abspath(__file__)
    start = os.path.dirname(here)  # .../vvg_client
    candidates = []
    cur = start
    for _ in range(6):
        if not cur:
            break
        candidates.append(cur)
        cur = os.path.dirname(cur)

    expanded = []
    seen = set()
    for directory in candidates:
        for path in [directory] + list(_res_mods_alternates(directory)):
            if not path:
                continue
            key = os.path.normcase(os.path.normpath(path))
            if key in seen:
                continue
            seen.add(key)
            if _has_pkg(path, 'vvg_client') and (
                    _has_pkg(path, 'protocol') or _has_pkg(path, 'sdk')):
                expanded.append(path)
    # Prefer directories that actually contain protocol/.
    expanded.sort(key=lambda d: (0 if _has_pkg(d, 'protocol') else 1, len(d)))
    return expanded


def ensure_paths():
    """Put the mod directory on sys.path so ``protocol`` / ``sdk`` import."""
    for directory in _candidate_mod_dirs():
        if not directory:
            continue
        if directory not in sys.path:
            sys.path.insert(0, directory)
        try:
            import protocol  # noqa: F401
            _log('sys.path ok (protocol) via %s' % directory)
            return directory
        except Exception:
            # Drop a bad path we just inserted so a later candidate wins.
            try:
                sys.path.remove(directory)
            except ValueError:
                pass
            continue
    # Fallback: still record the first plausible dir for diagnostics.
    candidates = _candidate_mod_dirs()
    if candidates:
        directory = candidates[0]
        if directory not in sys.path:
            sys.path.insert(0, directory)
        _log('sys.path += %s (protocol verify failed)' % directory)
        return directory
    _log('ensure_paths: no candidate mods directory')
    return None


def _client_mode():
    return (os.environ.get('VVG_CLIENT_MODE') or '').strip().lower()


def _identity_from_env():
    """Read player name / vehicle from environment (launcher sets these)."""
    name = (os.environ.get('VVG_PLAYER_NAME') or '').strip()
    vehicle = (os.environ.get('VVG_PLAYER_VEHICLE') or '').strip()
    host = (os.environ.get('VVG_SERVER_HOST') or '').strip() or None
    port_raw = (os.environ.get('VVG_SERVER_PORT') or '').strip()
    port = None
    if port_raw:
        try:
            port = int(port_raw)
        except ValueError:
            port = None
    mode = _client_mode()
    if mode == 'simulation_worker':
        return {
            'name': name or 'worker',
            'vehicle': 'worker',
            'host': host,
            'port': port,
            'role': 'worker',
        }
    return {
        'name': name or 'Player',
        'vehicle': vehicle or 'ussr:R05_LT',
        'host': host,
        'port': port,
        'role': 'player',
    }


def create_session(name=None, vehicle=None, host=None, port=None, role=None):
    # Prefer package-relative import (works inside gui.mods.vvg_client).
    try:
        from .session import ClientSession
    except (ImportError, ValueError):
        from vvg_client.session import ClientSession
    env = _identity_from_env()
    return ClientSession(
        name=name or env['name'],
        vehicle=vehicle or env['vehicle'],
        host=host or env['host'],
        port=port if port is not None else env['port'],
        role=role or env['role'],
    )


def _mark_worker_ready():
    """Touch VVG_WORKER_READY_MARKER so worker_starter exits its wait loop."""
    path = (os.environ.get('VVG_WORKER_READY_MARKER') or '').strip()
    if not path:
        return
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        handle = open(path, 'wb')
        try:
            handle.write(b'ok\n')
        finally:
            handle.close()
        _log('worker ready marker written: %s' % path)
    except Exception as exc:
        _log('worker ready marker failed: %s' % exc)



def init(name=None, vehicle=None, host=None, port=None, auto_connect=True):
    """Start the thin client. Never raises (game.init must not die)."""
    global _started, _session
    if _started:
        return _session

    try:
        ensure_paths()
    except Exception as path_error:
        _log('ensure_paths failed: %s' % path_error)

    try:
        from sdk import config
        server = config.get_server_address()
        _log('config server=%s:%s' % (server[0], server[1]))
    except Exception as config_error:
        _log('config load failed: %s' % config_error)

    try:
        _session = create_session(name=name, vehicle=vehicle,
                                  host=host, port=port)
    except Exception as session_error:
        _log('create_session failed: %s' % session_error)
        _session = None
        _started = True
        return None

    client = _session.client
    _log('session name=%s vehicle=%s target=%s:%s' % (
        client.name, client.vehicle, client.connection.host,
        client.connection.port))

    if auto_connect:
        try:
            welcome = _session.start()
        except Exception as start_error:
            _log('start failed: %s' % start_error)
            welcome = None
        if welcome is None:
            _log('handshake failed: %s' % _session.last_error)
        else:
            _log('handshake ok player_id=%s team=%s phase=%s role=%s' % (
                welcome.get('player_id'), welcome.get('team'),
                welcome.get('phase'), client.role))
            if client.role == 'worker' or _client_mode() == 'simulation_worker':
                _mark_worker_ready()

    try:
        try:
            from .hooks import bigworld_hooks
        except (ImportError, ValueError):
            from vvg_client.hooks import bigworld_hooks
        installed = bigworld_hooks.install(_session)
        _log('bigworld hooks installed=%s' % ('1' if installed else '0'))
    except Exception as hook_error:
        _log('hook install failed: %s' % hook_error)

    _started = True
    return _session


def fini():
    global _started, _session
    try:
        try:
            from .hooks import bigworld_hooks
        except (ImportError, ValueError):
            from vvg_client.hooks import bigworld_hooks
        bigworld_hooks.uninstall()
    except Exception:
        pass
    if _session is not None:
        try:
            _session.stop()
        except Exception as stop_error:
            _log('stop failed: %s' % stop_error)
    _session = None
    _started = False
    _log('fini')


def session():
    return _session


def is_started():
    return bool(_started)


__all__ = [
    'init',
    'fini',
    'session',
    'is_started',
    'ensure_paths',
    'create_session',
]
