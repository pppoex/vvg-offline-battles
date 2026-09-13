# -*- coding: utf-8 -*-
"""Minimal local HTTP status page for the thin client room.

Python 2/3 compatible BaseHTTP server. Bound to 127.0.0.1 only.
"""
from __future__ import absolute_import, division, print_function

import json
import socket
import sys
import threading

try:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from SocketServer import ThreadingMixIn
except ImportError:
    from socketserver import ThreadingMixIn

# Offline hangar already binds 18080 (shop). Must not collide.
DEFAULT_PORT = 19080
MAX_PORT_TRIES = 64

_LOG_PREFIX = '[VVG webui] '


def _log(message):
    try:
        sys.stdout.write(_LOG_PREFIX + str(message) + '\n')
        sys.stdout.flush()
    except Exception:
        pass


def find_free_port(host='127.0.0.1', start=DEFAULT_PORT, tries=MAX_PORT_TRIES):
    """Return first free TCP port in [start, start+tries)."""
    for port in range(int(start), int(start) + int(tries)):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, port))
            probe.close()
            return port
        except Exception:
            try:
                probe.close()
            except Exception:
                pass
    raise RuntimeError('no free web port near %s' % start)


class _ThreadedHTTP(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class WebController(object):
    """Adapts BattleClient / ClientSession to the status page."""

    def __init__(self, client, session=None):
        self.client = client
        self.session = session

    def get_status(self):
        client = self.client
        if client is None:
            return {
                'server': '?',
                'map': None,
                'phase': None,
                'round_id': 0,
                'host_player_id': None,
                'player_id': None,
                'name': None,
                'vehicle': None,
                'team': None,
                'connected': False,
                'is_host': False,
                'players': [],
            }
        players = []
        roster = getattr(client, 'roster', None)
        if isinstance(roster, dict):
            for row in roster.get('players') or ():
                players.append({
                    'player_id': row.get('player_id'),
                    'name': row.get('name'),
                    'team': row.get('team'),
                    'vehicle': row.get('vehicle'),
                    'ready': bool(row.get('ready')),
                })
        return {
            'server': '%s:%s' % (
                getattr(getattr(client, 'connection', None), 'host', '?'),
                getattr(getattr(client, 'connection', None), 'port', '?')),
            'map': getattr(client, 'map_name', None),
            'phase': getattr(client, 'phase', None),
            'round_id': getattr(client, 'round_id', 0),
            'host_player_id': getattr(client, 'host_player_id', None),
            'player_id': getattr(client, 'player_id', None),
            'name': getattr(client, 'name', None),
            'vehicle': getattr(client, 'vehicle', None),
            'team': getattr(client, 'team', None),
            'connected': bool(getattr(client, 'connected', False)),
            'is_host': bool(client.is_host()) if hasattr(client, 'is_host') else False,
            'players': players,
        }

    def request_start(self):
        client = self.client
        if client is None:
            return False, 'no_client'
        if not getattr(client, 'connected', False):
            return False, 'not_connected'
        if hasattr(client, 'is_host') and not client.is_host():
            return False, 'not_host'
        if hasattr(client, 'send_start_battle'):
            ok = client.send_start_battle()
            return bool(ok), '' if ok else 'send_failed'
        return False, 'no_start_api'

    def request_connect(self):
        session = getattr(self, 'session', None)
        client = self.client
        if session is not None and hasattr(session, 'start'):
            if client is not None and getattr(client, 'connected', False):
                return True
            welcome = session.start(timeout=4.0)
            return welcome is not None
        if client is not None and hasattr(client, 'connect_and_handshake'):
            if getattr(client, 'connected', False):
                return True
            welcome = client.connect_and_handshake(timeout=4.0)
            return welcome is not None
        return False

    def request_leave(self):
        owner = getattr(self, 'session', None)
        if owner is not None and hasattr(owner, 'leave_battle'):
            return bool(owner.leave_battle())
        client = self.client
        if client is not None and hasattr(client, 'send_leave_battle'):
            return bool(client.send_leave_battle())
        return False


class StatusWebServer(object):
    """Owns one local HTTP server thread."""

    def __init__(self, controller, host='127.0.0.1', port=None):
        self.controller = controller
        self.host = host
        self._port = int(port) if port else None
        self._http = None
        self._thread = None

    @property
    def port(self):
        if self._http is not None:
            return self._http.server_address[1]
        return self._port

    @property
    def url(self):
        return 'http://%s:%s/' % (self.host, self.port or DEFAULT_PORT)

    def start(self):
        if self._http is not None:
            return self.url
        controller = self.controller
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                try:
                    _log(fmt % args)
                except Exception:
                    pass

            def _send(self, code, body, content_type='text/html; charset=utf-8'):
                if not isinstance(body, bytes):
                    body = body.encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = (self.path or '/').split('?', 1)[0]
                if path in ('/', '/index.html'):
                    try:
                        status = controller.get_status()
                    except Exception as exc:
                        self._send(500, 'status error: %s' % exc, 'text/plain; charset=utf-8')
                        return
                    self._send(200, render_status_html(status, outer.url))
                    return
                if path == '/status.json':
                    try:
                        payload = json.dumps(controller.get_status())
                    except Exception as exc:
                        self._send(500, json.dumps({'error': str(exc)}), 'application/json')
                        return
                    self._send(200, payload, 'application/json')
                    return
                self._send(404, 'not found', 'text/plain; charset=utf-8')

            def do_POST(self):
                path = (self.path or '/').split('?', 1)[0]
                length = 0
                try:
                    length = int(self.headers.get('Content-Length') or 0)
                except Exception:
                    length = 0
                if length > 0:
                    try:
                        self.rfile.read(length)
                    except Exception:
                        pass
                if path == '/start':
                    try:
                        status = controller.get_status()
                    except Exception as exc:
                        self._send(500, json.dumps({'ok': False, 'error': str(exc)}),
                                   'application/json')
                        return
                    if not status.get('is_host'):
                        self._send(403, json.dumps({'ok': False, 'error': 'not_host'}),
                                   'application/json')
                        return
                    try:
                        ok, reason = controller.request_start()
                    except Exception as exc:
                        ok, reason = False, str(exc)
                    code = 200 if ok else 400
                    self._send(code, json.dumps({
                        'ok': bool(ok),
                        'error': reason or None,
                    }), 'application/json')
                    return
                if path == '/leave':
                    try:
                        ok = bool(controller.request_leave())
                    except Exception as exc:
                        self._send(500, json.dumps({'ok': False, 'error': str(exc)}),
                                   'application/json')
                        return
                    self._send(200 if ok else 400, json.dumps({'ok': ok}),
                               'application/json')
                    return
                if path == '/connect':
                    try:
                        ok = bool(controller.request_connect())
                    except Exception as exc:
                        self._send(500, json.dumps({'ok': False, 'error': str(exc)}),
                                   'application/json')
                        return
                    self._send(200 if ok else 400, json.dumps({'ok': ok}),
                               'application/json')
                    return
                self._send(404, 'not found', 'text/plain; charset=utf-8')

        port = self._port if self._port is not None else find_free_port(self.host)
        self._http = _ThreadedHTTP((self.host, port), Handler)
        self._port = self._http.server_address[1]
        # Py2.7 Thread does not accept daemon= kwarg (log: unexpected keyword).
        self._thread = threading.Thread(
            target=self._http.serve_forever,
            kwargs={'poll_interval': 0.2},
            name='vvg-webui')
        try:
            self._thread.daemon = True
        except Exception:
            pass
        self._thread.start()
        _log('listening %s' % self.url)
        return self.url

    def stop(self):
        http = self._http
        self._http = None
        if http is not None:
            try:
                http.shutdown()
            except Exception:
                pass
            try:
                http.server_close()
            except Exception:
                pass
        self._thread = None


def render_status_html(status, self_url):
    """Return a small UTF-8 HTML status document."""
    players = status.get('players') or []
    rows = []
    for row in players:
        rows.append(
            '<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td></tr>'.format(
                _esc(row.get('player_id')),
                _esc(row.get('name')),
                _esc(row.get('team')),
                _esc(row.get('vehicle')),
                'yes' if row.get('ready') else 'no',
            ))
    if not rows:
        rows.append('<tr><td colspan="5">(empty)</td></tr>')
    connected = bool(status.get('connected'))
    is_host = bool(status.get('is_host'))
    can_start = bool(is_host and connected and status.get('phase') in (None, 'waiting', 'finished'))
    start_disabled = '' if can_start else ' disabled'
    connect_disabled = '' if not connected else ' disabled'
    is_host_txt = 'yes' if is_host else 'no'
    connected_txt = 'yes' if connected else 'no'
    phase = status.get('phase') or '?'
    hint = ''
    if not connected:
        hint = '未连接 sim-worker。请先启动：python -m launcher server，然后点「连接服务器」。'
    elif not is_host:
        hint = '已连接但不是房主。只有房主（首名玩家）可以点开始战斗。'
    elif phase not in ('waiting', 'finished', None):
        hint = '当前阶段=%s，需等待/结束后才能开战。' % phase
    else:
        hint = '已就绪：你是房主，可以开始战斗。'
    return (
        '<!DOCTYPE html>\n'
        '<html lang="zh-CN"><head><meta charset="utf-8">'
        '<title>VVG Room</title>'
        '<meta http-equiv="refresh" content="3">'
        '<style>'
        'body{font-family:sans-serif;margin:24px;background:#111;color:#eee}'
        'table{border-collapse:collapse;width:100%;max-width:720px}'
        'td,th{border:1px solid #444;padding:6px 8px;text-align:left}'
        'button{margin:12px 8px 0 0;padding:10px 16px;font-size:16px}'
        'button:disabled{opacity:0.4}'
        '.muted{color:#999}'
        '.hint{color:#fc6;margin:12px 0}'
        '</style></head><body>'
        '<h1>VVG 联机房间</h1>'
        '<p class="hint">' + _esc(hint) + '</p>'
        '<ul>'
        '<li>本页: <code>' + _esc(self_url) + '</code></li>'
        '<li>服务器: ' + _esc(status.get('server')) + '</li>'
        '<li>地图: ' + _esc(status.get('map')) + '</li>'
        '<li>阶段: ' + _esc(phase) + '</li>'
        '<li>回合: ' + _esc(status.get('round_id')) + '</li>'
        '<li>房主 ID: ' + _esc(status.get('host_player_id')) + '</li>'
        '<li>本机: ' + _esc(status.get('name')) + ' (player_id='
        + _esc(status.get('player_id')) + ', host=' + is_host_txt + ')</li>'
        '<li>连接 sim-worker: ' + connected_txt + '</li>'
        '</ul>'
        '<table><tr><th>ID</th><th>名字</th><th>队伍</th><th>车辆</th><th>就绪</th></tr>'
        + ''.join(rows) +
        '</table>'
        '<button id="connect" onclick="doConnect()"' + connect_disabled + '>连接服务器</button>'
        '<button id="start" onclick="doStart()"' + start_disabled + '>开始战斗</button>'
        '<p id="msg" class="muted"></p>'
        '<script>'
        'function doConnect(){'
        'fetch("/connect",{method:"POST"}).then(function(r){return r.json();})'
        '.then(function(j){document.getElementById("msg").textContent=j.ok?"connected":("connect failed");'
        'location.reload();})'
        '.catch(function(e){document.getElementById("msg").textContent=String(e);});}'
        'function doStart(){'
        'fetch("/start",{method:"POST"}).then(function(r){return r.json();})'
        '.then(function(j){document.getElementById("msg").textContent=j.ok?"started":(j.error||"failed");'
        'if(j.ok)location.reload();})'
        '.catch(function(e){document.getElementById("msg").textContent=String(e);});}'
        '</script>'
        '</body></html>'
    )


def _esc(value):
    if value is None:
        return ''
    text = value if isinstance(value, str) else str(value)
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


__all__ = [
    'DEFAULT_PORT',
    'find_free_port',
    'WebController',
    'StatusWebServer',
    'render_status_html',
]
