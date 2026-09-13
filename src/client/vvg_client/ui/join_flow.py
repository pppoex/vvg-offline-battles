# -*- coding: utf-8 -*-
"""Battle! click orchestration: ensure connect, start local web, open browser."""
from __future__ import absolute_import, division, print_function

import sys
import webbrowser

try:
    from .. import join_gate
    from ..webui.server import StatusWebServer, WebController
except (ImportError, ValueError):
    from vvg_client import join_gate
    from vvg_client.webui.server import StatusWebServer, WebController

LOG_PREFIX = '[VVG join_flow] '

_web = None
_controller = None


def _log(message):
    try:
        sys.stdout.write(LOG_PREFIX + str(message) + '\n')
        sys.stdout.flush()
    except Exception:
        pass


def _get_session():
    try:
        from vvg_client import bootstrap
        return bootstrap.session()
    except Exception:
        return None


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
    session = session or _get_session()
    if session is None:
        return None
    if _web is not None:
        return _web.url
    _controller = WebController(session.client)
    _web = StatusWebServer(_controller)
    try:
        url = _web.start()
    except Exception as exc:
        _log('web start failed: %s' % exc)
        _web = None
        return None
    _log('web at %s' % url)
    return url


def open_browser(url):
    if not url:
        return False
    try:
        webbrowser.open(url)
        _log('browser open %s' % url)
        return True
    except Exception as exc:
        _log('browser open failed: %s' % exc)
        return False


def on_battle_clicked(veh_inv_id=None, arena_type_id=0):
    """join_gate handler: open local room web instead of Offline battle."""
    _log('battle click vehInvID=%s arenaTypeID=%s' % (veh_inv_id, arena_type_id))
    session = _ensure_session()
    if session is None:
        return None
    url = start_room_web(session)
    if url:
        open_browser(url)
    return url


def stop_room_web():
    global _web, _controller
    if _web is not None:
        try:
            _web.stop()
        except Exception:
            pass
    _web = None
    _controller = None


def install():
    join_gate.set_handler(on_battle_clicked)
    ok = join_gate.install()
    _log('join_gate installed=%s' % ok)
    return ok


def web_url():
    return _web.url if _web is not None else None


__all__ = [
    'install',
    'on_battle_clicked',
    'start_room_web',
    'stop_room_web',
    'open_browser',
    'web_url',
]
