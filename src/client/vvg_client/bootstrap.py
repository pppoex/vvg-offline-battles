# -*- coding: utf-8 -*-
"""Mod bootstrap — ensure paths, optionally install BigWorld hooks.

Called from ``mod_vvg_client.init()``. Safe to call twice (idempotent).
Works without BigWorld so host tests can import the same code path.
"""
from __future__ import absolute_import, division, print_function

import os
import sys

LOG_PREFIX = '[VVG thin client] '

_started = False
_session = None


def _log(message):
    try:
        text = LOG_PREFIX + str(message)
        sys.stdout.write(text + '\n')
        sys.stdout.flush()
    except Exception:
        pass


def ensure_paths():
    """Put the mods directory on sys.path so ``protocol`` is importable.

    Deployed layout::

        res_mods/2.3.1.2/scripts/client/gui/mods/
            mod_vvg_client.py
            vvg_client/
            protocol/          # vendored copy of src/protocol

    Host layout leaves ``src`` on PYTHONPATH already; this is a no-op then.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    # .../mods/vvg_client  ->  .../mods
    mods_dir = os.path.dirname(here)
    if mods_dir and mods_dir not in sys.path:
        sys.path.insert(0, mods_dir)
        _log('sys.path += %s' % mods_dir)
    # Host workspace: .../src/client -> also need .../src for protocol/sdk
    # when someone imported via file path without PYTHONPATH.
    client_dir = os.path.dirname(here)
    src_dir = os.path.dirname(client_dir)
    if os.path.basename(client_dir) == 'client' and os.path.isdir(
            os.path.join(src_dir, 'protocol')):
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
            _log('sys.path += %s' % src_dir)


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
    return {
        'name': name or 'Player',
        'vehicle': vehicle or 'ussr:R05_LT',
        'host': host,
        'port': port,
    }


def create_session(name=None, vehicle=None, host=None, port=None):
    from vvg_client.session import ClientSession
    env = _identity_from_env()
    return ClientSession(
        name=name or env['name'],
        vehicle=vehicle or env['vehicle'],
        host=host or env['host'],
        port=port if port is not None else env['port'],
    )


def init(name=None, vehicle=None, host=None, port=None, auto_connect=True):
    """Start the thin client (connect unless disabled)."""
    global _started, _session
    if _started:
        return _session
    ensure_paths()

    try:
        from sdk import config
        server = config.get_server_address()
        _log('config server=%s:%s' % (server[0], server[1]))
    except Exception as config_error:
        _log('config load failed: %s' % config_error)

    _session = create_session(name=name, vehicle=vehicle, host=host, port=port)
    client = _session.client
    _log('session name=%s vehicle=%s target=%s:%s' % (
        client.name, client.vehicle, client.connection.host,
        client.connection.port))

    if auto_connect:
        welcome = _session.start()
        if welcome is None:
            _log('handshake failed: %s' % _session.last_error)
        else:
            _log('handshake ok player_id=%s team=%s phase=%s' % (
                welcome.get('player_id'), welcome.get('team'),
                welcome.get('phase')))

    try:
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
