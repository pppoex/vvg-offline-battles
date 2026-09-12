# -*- coding: utf-8 -*-
"""Initialize the multi-client instance guard once GUI mods load.

Mirrors the 0.9.22 offline_lan_0922 bootstrap: call
``instance_guard.release_if_requested()`` as early as the mod entry allows,
before any other scheduling.  Failures are logged and never abort the client
unless the environment explicitly demands multi-client mode and release fails
in a way the launcher can observe (we only refuse for simulation workers).
"""
from __future__ import print_function

import os
import sys

try:
    from gui.mods.vvg_instance_guard import instance_guard
except ImportError:
    # Deployed as a flat package under res_mods without the gui.mods prefix
    # (fallback for unusual path setups).
    from vvg_instance_guard import instance_guard


LOG_PREFIX = '[VVG instance guard] '

_started = False
_client_guard_released = False
_release_error = None


def _log(message):
    try:
        sys.stdout.write(LOG_PREFIX + message + '\n')
        sys.stdout.flush()
    except Exception:
        pass


def _client_mode():
    try:
        return (os.environ.get('VVG_CLIENT_MODE') or '').strip()
    except AttributeError:
        return ''


def init():
    global _started, _client_guard_released, _release_error
    if _started:
        return
    _started = True

    mode = _client_mode()
    _log('init mode=%s allow_multi=%s' % (
        mode or 'unknown',
        '1' if instance_guard._multiple_clients_requested(os.environ)
        else '0'))

    try:
        _client_guard_released = bool(instance_guard.release_if_requested())
        _release_error = None
    except Exception as error:
        _client_guard_released = False
        _release_error = error
        _log('release failed: %s' % error)

    if _client_guard_released:
        _log('released startup/WGC mutexes for multi-client')
    elif _release_error is not None:
        _log('client guard release error: %s' % _release_error)
    else:
        _log('multi-client not requested; startup mutex left intact')

    # Hidden simulation workers must never enter a second "already running"
    # interactive path.  If release failed, refuse early so the launcher can
    # surface the failure instead of a stuck dialog.
    if mode == 'simulation_worker' and instance_guard.\
            _multiple_clients_requested(os.environ) and not _client_guard_released:
        _log('simulation worker startup refused: guard release incomplete')
        try:
            import BigWorld
            BigWorld.quit()
        except Exception as quit_error:
            _log('BigWorld.quit failed: %s' % quit_error)


def fini():
    global _started, _client_guard_released, _release_error
    _started = False
    _client_guard_released = False
    _release_error = None
    _log('fini')


def guard_released():
    """Return True when this process opted in and released successfully."""
    return bool(_client_guard_released)
