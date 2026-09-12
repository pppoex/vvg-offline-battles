# -*- coding: utf-8 -*-
"""Optional BigWorld hooks — schedule ClientSession.pump/tick on the engine.

Outside the game (unit / integration tests) ``install`` is a no-op and
returns False. Inside BigWorld, ``BigWorld.callback`` drives the session.
"""
from __future__ import absolute_import, division, print_function

_installed = False
_session = None
_callback_token = None


def _log(message):
    try:
        from sdk import log
        log.info('%s', message)
    except Exception:
        try:
            print('[VVG/hooks] %s' % message)
        except Exception:
            pass


def _import_bigworld():
    try:
        import BigWorld
        return BigWorld
    except Exception:
        return None


def _schedule(bigworld, session, delay=0.0):
    """Register a BigWorld.callback that re-arms itself each frame."""
    callback = getattr(bigworld, 'callback', None)
    if not callable(callback):
        _log('BigWorld.callback missing')
        return False

    def _frame():
        global _callback_token
        try:
            if session is not None and session.connected:
                session.tick(dt=1.0 / 30.0)
        except Exception as exc:
            _log('session tick failed: %s' % exc)
        try:
            if _session is session and session is not None and session.connected:
                _callback_token = callback(delay, _frame)
        except Exception as exc:
            _log('reschedule failed: %s' % exc)

    try:
        _callback_token = callback(delay, _frame)
        return True
    except Exception as exc:
        _log('BigWorld.callback failed: %s' % exc)
        return False


def install(session):
    """Attach session to BigWorld's frame loop. Returns True if scheduled."""
    global _installed, _session, _callback_token
    bigworld = _import_bigworld()
    if bigworld is None:
        _log('BigWorld not available; hooks skipped')
        return False
    if _installed:
        _session = session
        return True
    _session = session
    ok = _schedule(bigworld, session, delay=0.0)
    _installed = bool(ok)
    if ok:
        _log('BigWorld frame hook installed')
    return ok


def uninstall():
    global _installed, _session, _callback_token
    _session = None
    _callback_token = None
    _installed = False
    _log('hooks uninstalled')


def is_installed():
    return bool(_installed)


def current_session():
    return _session


__all__ = [
    'install',
    'uninstall',
    'is_installed',
    'current_session',
]
