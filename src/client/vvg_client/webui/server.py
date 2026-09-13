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
            'known_maps': list(getattr(client, 'known_maps', None) or []),
            'last_end_reason': getattr(client, 'last_end_reason', None),
        }

    def request_start(self, map_name=None, round_seconds=None):
        client = self.client
        if client is None:
            return False, 'no_client'
        if not getattr(client, 'connected', False):
            return False, 'not_connected'
        if hasattr(client, 'is_host') and not client.is_host():
            return False, 'not_host'
        if hasattr(client, 'send_start_battle'):
            ok = client.send_start_battle(
                round_seconds=round_seconds, map_name=map_name)
            return bool(ok), '' if ok else 'send_failed'
        return False, 'no_start_api'

    def request_select_map(self, map_name):
        client = self.client
        if client is None:
            return False, 'no_client'
        if not getattr(client, 'connected', False):
            return False, 'not_connected'
        if hasattr(client, 'is_host') and not client.is_host():
            return False, 'not_host'
        if hasattr(client, 'send_select_map'):
            ok = client.send_select_map(map_name)
            return bool(ok), '' if ok else 'send_failed'
        return False, 'no_select_map_api'

    def request_connect(self):
        session = getattr(self, 'session', None)
        client = self.client
        if client is not None and getattr(client, 'connected', False):
            return True, 'already_connected'
        try:
            if session is not None and hasattr(session, 'start'):
                welcome = session.start(timeout=4.0)
            elif client is not None and hasattr(client, 'connect_and_handshake'):
                welcome = client.connect_and_handshake(timeout=4.0)
            else:
                return False, 'no_session_api'
        except Exception as exc:
            return False, 'exception:%s' % exc
        if welcome is not None:
            return True, 'ok'
        err = None
        if session is not None:
            err = getattr(session, 'last_error', None)
        if not err and client is not None:
            err = getattr(client, 'last_error', None)
        return False, err or 'handshake_failed'

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
                body = b''
                if length > 0:
                    try:
                        body = self.rfile.read(length)
                    except Exception:
                        body = b''
                form = {}
                if body:
                    try:
                        text = body.decode('utf-8', 'replace')
                        for part in text.split('&'):
                            if '=' in part:
                                key, value = part.split('=', 1)
                                form[key.strip()] = value.strip()
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
                    map_name = form.get('map') or None
                    try:
                        ok, reason = controller.request_start(map_name=map_name)
                    except Exception as exc:
                        ok, reason = False, str(exc)
                    code = 200 if ok else 400
                    self._send(code, json.dumps({
                        'ok': bool(ok),
                        'error': reason or None,
                    }), 'application/json')
                    return
                if path == '/map':
                    map_name = form.get('map') or ''
                    try:
                        ok, reason = controller.request_select_map(map_name)
                    except Exception as exc:
                        ok, reason = False, str(exc)
                    self._send(200 if ok else 400, json.dumps({
                        'ok': bool(ok),
                        'error': reason or None,
                        'map': map_name,
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
                        ok, reason = controller.request_connect()
                    except Exception as exc:
                        self._send(500, json.dumps({'ok': False, 'error': str(exc)}),
                                   'application/json')
                        return
                    payload = {'ok': bool(ok)}
                    if ok:
                        payload['reason'] = reason
                    else:
                        payload['error'] = reason
                    self._send(200 if ok else 400, json.dumps(payload),
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
    phase = status.get('phase') or '?'
    in_waiting = phase in (None, 'waiting', 'finished')
    can_start = bool(is_host and connected and in_waiting)
    start_disabled = '' if can_start else ' disabled'
    connect_disabled = '' if not connected else ' disabled'
    map_disabled = '' if (is_host and connected and in_waiting) else ' disabled'
    is_host_txt = 'yes' if is_host else 'no'
    connected_txt = 'yes' if connected else 'no'
    pid = status.get('player_id')
    host_id = status.get('host_player_id')
    current_map = status.get('map') or 'vvg_default'
    maps = status.get('known_maps') or []
    if current_map and current_map not in maps:
        maps = [current_map] + list(maps)
    if not maps:
        maps = [current_map]
    options = []
    for name in maps:
        selected = ' selected' if name == current_map else ''
        options.append(
            '<option value="%s"%s>%s</option>' % (
                _esc(name), selected, _esc(name)))
    last_end = status.get('last_end_reason')
    end_line = ''
    if last_end:
        end_line = '<li>上次结束: %s</li>' % _esc(last_end)
    hint = ''
    if not connected:
        hint = ('未连接 sim-worker。请先运行 python -m launcher server，'
                '再点「连接服务器」。')
    elif host_id is None:
        hint = '已连接但服务器未下发 host_player_id（协议异常）。'
    elif not is_host:
        hint = ('本机 player_id=%s，房主是 %s（先成功连上的玩家）。'
                % (pid, host_id))
    elif not in_waiting:
        hint = '当前阶段=%s，对局进行中；结束后会自动回到等待。' % phase
    else:
        hint = '已连接且你是房主（player_id=%s）。可选图后开始战斗。' % pid
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
        'select{margin:12px 8px 0 0;padding:8px;font-size:16px}'
        '.muted{color:#999}'
        '.hint{color:#fc6;margin:12px 0}'
        '</style></head><body>'
        '<h1>VVG 联机房间</h1>'
        '<p class="hint">' + _esc(hint) + '</p>'
        '<ul>'
        '<li>本页: <code>' + _esc(self_url) + '</code></li>'
        '<li>服务器: ' + _esc(status.get('server')) + '</li>'
        '<li>地图: ' + _esc(current_map) + '</li>'
        '<li>阶段: ' + _esc(phase) + '</li>'
        '<li>回合: ' + _esc(status.get('round_id')) + '</li>'
        '<li>房主 ID: ' + _esc(host_id) + '</li>'
        '<li>本机: ' + _esc(status.get('name')) + ' (player_id='
        + _esc(pid) + ', host=' + is_host_txt + ')</li>'
        '<li>连接 sim-worker: ' + connected_txt + '</li>'
        + end_line +
        '</ul>'
        '<table><tr><th>ID</th><th>名字</th><th>队伍</th><th>车辆</th><th>就绪</th></tr>'
        + ''.join(rows) +
        '</table>'
        '<label>地图 <select id="map">' + ''.join(options) + '</select></label>'
        '<button id="setmap" onclick="doMap()"' + map_disabled + '>应用地图</button>'
        '<button id="connect" onclick="doConnect()"' + connect_disabled + '>连接服务器</button>'
        '<button id="start" onclick="doStart()"' + start_disabled + '>开始战斗</button>'
        '<button id="leave" onclick="doLeave()">离开战斗</button>'
        '<p id="msg" class="muted"></p>'
        '<script>'
        'function doConnect(){'
        'fetch("/connect",{method:"POST"}).then(function(r){return r.json();})'
        '.then(function(j){document.getElementById("msg").textContent=j.ok?("connected "+(j.reason||"")):("connect failed: "+(j.error||""));'
        'location.reload();})'
        '.catch(function(e){document.getElementById("msg").textContent=String(e);});}'
        'function doMap(){'
        'var m=document.getElementById("map").value;'
        'fetch("/map",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        'body:"map="+encodeURIComponent(m)})'
        '.then(function(r){return r.json();})'
        '.then(function(j){document.getElementById("msg").textContent=j.ok?("map="+m):("map failed: "+(j.error||""));'
        'location.reload();})'
        '.catch(function(e){document.getElementById("msg").textContent=String(e);});}'
        'function doStart(){'
        'var m=document.getElementById("map").value;'
        'fetch("/start",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},'
        'body:"map="+encodeURIComponent(m)})'
        '.then(function(r){return r.json();})'
        '.then(function(j){document.getElementById("msg").textContent=j.ok?"started":(j.error||"failed");'
        'if(j.ok)location.reload();})'
        '.catch(function(e){document.getElementById("msg").textContent=String(e);});}'
        'function doLeave(){'
        'fetch("/leave",{method:"POST"}).then(function(r){return r.json();})'
        '.then(function(j){document.getElementById("msg").textContent=j.ok?"left":(j.error||"failed");'
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
