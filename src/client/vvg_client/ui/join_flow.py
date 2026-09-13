# -*- coding: utf-8 -*-
"""Battle! click orchestration: ensure connect, start local web, open browser."""
from __future__ import absolute_import, division, print_function

import os
import sys

try:
    from .. import join_gate
    from ..webui.server import StatusWebServer, WebController
except (ImportError, ValueError):
    from vvg_client import join_gate
    from vvg_client.webui.server import StatusWebServer, WebController

LOG_PREFIX = '[VVG join_flow] '

_web = None
_controller = None
_retries = 0
_MAX_RETRIES = 30
_browser_last_url = None
_browser_ok = False


def _log(message):
    try:
        sys.stdout.write(LOG_PREFIX + str(message) + '\n')
        sys.stdout.flush()
    except Exception:
        pass


def _get_session():
    """Return the live ClientSession from whichever bootstrap module holds it."""
    candidates = []
    try:
        from .. import bootstrap as rel_bootstrap
        candidates.append(rel_bootstrap)
    except Exception:
        pass
    try:
        from gui.mods.vvg_client import bootstrap as game_bootstrap
        candidates.append(game_bootstrap)
    except Exception:
        pass
    try:
        from vvg_client import bootstrap as top_bootstrap
        candidates.append(top_bootstrap)
    except Exception:
        pass

    if not candidates:
        _log('bootstrap module not found')
        return None

    seen = set()
    for bootstrap in candidates:
        key = id(bootstrap)
        if key in seen:
            continue
        seen.add(key)
        try:
            session = bootstrap.session()
        except Exception as exc:
            _log('bootstrap.session() failed on %s: %s' % (
                getattr(bootstrap, '__name__', '?'), exc))
            continue
        if session is not None:
            _log('session found on %s' % getattr(bootstrap, '__name__', '?'))
            return session

    _log('no session on any bootstrap module (%d candidates)' % len(candidates))
    return None


def _hide_waiting():
    """Dismiss stock joining/waiting overlay after intercept."""
    try:
        from gui.Scaleform import Waiting
        hide = getattr(Waiting, 'hide', None)
        if callable(hide):
            try:
                hide()
            except TypeError:
                hide('join')
            _log('Waiting.hide() called')
            return True
    except Exception as exc:
        _log('Waiting.hide failed: %s' % exc)
    return False


def _ensure_session():
    session = _get_session()
    if session is None:
        _log('no session yet')
        return None
    if not session.client.connected:
        try:
            welcome = session.start(timeout=3.0)
            _log('lazy connect welcome=%s' % ('ok' if welcome else 'fail'))
        except Exception as exc:
            _log('lazy connect error: %s' % exc)
    return session


def start_room_web(session=None):
    """Start (or reuse) status web bound to the BattleClient."""
    global _web, _controller
    session = session if session is not None else _get_session()
    if _web is not None:
        return _web.url
    client = getattr(session, 'client', None) if session is not None else None
    try:
        _controller = WebController(client, session=session)
        _web = StatusWebServer(_controller)
        url = _web.start()
    except Exception as exc:
        _log('web start failed: %s' % exc)
        _web = None
        _controller = None
        return None
    _log('web at %s (session=%s client=%s)' % (
        url, session is not None, client is not None))
    return url


def open_browser(url):
    """Open URL in the system browser. Game process often needs ShellExecute."""
    global _browser_last_url, _browser_ok
    if not url:
        return False
    _browser_last_url = url
    _log('open_browser %s' % url)

    # 1) Windows ShellExecute via os.startfile (no ctypes needed)
    try:
        if os.name == 'nt' and hasattr(os, 'startfile'):
            os.startfile(url)
            _browser_ok = True
            _log('browser via os.startfile')
            return True
    except Exception as exc:
        _log('os.startfile failed: %s' % exc)

    # 2) cmd start
    try:
        if os.name == 'nt':
            import subprocess
            subprocess.Popen(
                ['cmd', '/c', 'start', '', url],
                close_fds=True,
                shell=False)
            _browser_ok = True
            _log('browser via cmd start')
            return True
    except Exception as exc:
        _log('cmd start failed: %s' % exc)

    # 3) webbrowser fallback
    try:
        import webbrowser
        opened = webbrowser.open(url)
        _browser_ok = bool(opened)
        _log('browser via webbrowser.open -> %s' % opened)
        return bool(opened)
    except Exception as exc:
        _log('webbrowser failed: %s' % exc)

    _log('all browser methods failed; open manually: %s' % url)
    return False


def on_battle_clicked(veh_inv_id=None, arena_type_id=0):
    """join_gate handler: open local room web instead of Offline battle."""
    global _retries
    _log('battle click vehInvID=%s arenaTypeID=%s' % (veh_inv_id, arena_type_id))
    _hide_waiting()
    try:
        session = _ensure_session()
        url = start_room_web(session)
        if url:
            open_browser(url)
        else:
            _log('web url is None after start_room_web')
            if session is None:
                _schedule_retry_install()
        return url
    except Exception as exc:
        _log('on_battle_clicked failed: %s' % exc)
        return None


def stop_room_web():
    global _web, _controller
    if _web is not None:
        try:
            _web.stop()
        except Exception:
            pass
    _web = None
    _controller = None


def _schedule_retry_install():
    """LobbyHeader may not be importable at first bootstrap.init."""
    global _retries
    if _retries >= _MAX_RETRIES:
        return
    _retries += 1

    def _retry():
        try:
            join_gate.install()
            _log('retry install #%d fight=%s offline=%s' % (
                _retries,
                join_gate.fight_button_installed(),
                join_gate.is_installed()))
        except Exception as exc:
            _log('retry install failed: %s' % exc)
        if _retries < _MAX_RETRIES:
            _arm_callback(2.0, _retry)

    _arm_callback(2.0, _retry)


def _arm_callback(delay, fn):
    try:
        import BigWorld
        callback = getattr(BigWorld, 'callback', None)
        if callable(callback):
            callback(delay, fn)
            return True
    except Exception as exc:
        _log('BigWorld.callback unavailable: %s' % exc)
    return False


def install():
    global _retries
    join_gate.set_handler(on_battle_clicked)
    ok = join_gate.install()
    _log('join_gate install fight=%s offline=%s' % (
        join_gate.fight_button_installed(), join_gate.is_installed()))
    # Keep retrying until fightClick is patched (lobby may load later).
    if not join_gate.fight_button_installed():
        _retries = 0
        _schedule_retry_install()
    return ok or join_gate.fight_button_installed()


def leave_to_garage():
    session = _get_session()
    if session is None:
        _log('leave_to_garage: no session')
        return False
    try:
        ok = session.leave_battle()
        _log('leave_to_garage -> %s' % ok)
        return ok
    except Exception as exc:
        _log('leave_to_garage failed: %s' % exc)
        return False


def web_url():
    return _web.url if _web is not None else None


def last_browser_url():
    return _browser_last_url


def browser_ok():
    return _browser_ok


__all__ = [
    'install',
    'on_battle_clicked',
    'start_room_web',
    'stop_room_web',
    'open_browser',
    'leave_to_garage',
    'web_url',
    'last_browser_url',
    'browser_ok',
]
