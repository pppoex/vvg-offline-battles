# -*- coding: utf-8 -*-
"""TCP 服务器 — 握手、消息分发、roster / snapshot 广播。

复用 ``protocol`` 的 serializer / messages / capabilities，不另起协议。
"""
from __future__ import absolute_import, division, print_function

import socket
import socketserver
import threading
import time

from protocol.capabilities import negotiate
from protocol.constants import (
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
    ERROR_INVALID_HELLO,
    ERROR_JOIN_REJECTED,
    ERROR_PROTOCOL_MISMATCH,
    ERROR_UNSUPPORTED_CAPABILITIES,
    ERROR_UNSUPPORTED_ROLE,
    MSG_BATTLE_READY,
    MSG_HELLO,
    MSG_INPUT,
    MSG_LEAVE,
    MSG_LEAVE_BATTLE,
    MSG_PING,
    MSG_SELECT_TEAM,
    MSG_SELECT_VEHICLE,
    MSG_START_BATTLE,
    PHASE_BATTLE,
    PHASE_WAITING,
    ROLE_PLAYER,
    PROTOCOL_VERSION,
)
from protocol.messages import (
    ProtocolError,
    build_error,
    build_pong,
    build_roster,
    build_snapshot,
    build_start_denied,
    build_team_denied,
    build_welcome,
    message_type_of,
)
from protocol.serializer import LineDecoder, encode_message
from sim_worker.room.room import Room
from sim_worker.tick import TickLoop


class GameWorld(object):
    """房间 + 广播 + tick 钩子。由 GameServer 与 TickLoop 共享。"""

    def __init__(self, map_name='vvg_default', team_size=15,
                 server_capabilities=None):
        from protocol.capabilities import DEFAULT_SERVER_CAPABILITIES

        self.lock = threading.RLock()
        self.running = True
        self.room = Room(map_name=map_name, team_size=team_size)
        self.server_capabilities = list(
            server_capabilities if server_capabilities is not None
            else DEFAULT_SERVER_CAPABILITIES)
        self._sessions = {}
        self._by_player_id = {}
        self._tick = 0
        self._server = None

    def bind_server(self, server):
        self._server = server

    # --- 会话注册 -----------------------------------------------------------

    def register_session(self, session):
        with self.lock:
            self._sessions[id(session)] = session
            self._by_player_id[session.player_id] = session

    def unregister_session(self, session):
        with self.lock:
            self._sessions.pop(id(session), None)
            self._by_player_id.pop(session.player_id, None)
            self.room.leave(session.player_id)

    def session_for(self, player_id):
        with self.lock:
            return self._by_player_id.get(player_id)

    def all_sessions(self):
        with self.lock:
            return [s for s in self._sessions.values() if s.connected]

    # --- tick / 快照 --------------------------------------------------------

    def tick_once(self, dt, server_tick):
        with self.lock:
            self._tick = server_tick
            self.room.tick_once(dt, server_tick)

    def should_snapshot(self, server_tick):
        with self.lock:
            return self.room.phase == PHASE_BATTLE

    def broadcast_snapshot(self, server_tick):
        with self.lock:
            if self.room.phase != PHASE_BATTLE:
                return
            message = build_snapshot(
                self.room.round_id,
                server_tick,
                self._now_ms(),
                payload=self.room.snapshot_payload(),
                state_revision=self.room.state_revision,
            )
        self.broadcast(message)

    @property
    def server_tick(self):
        return self._tick

    def server_time_ms(self):
        return self._now_ms()

    # --- 广播 ---------------------------------------------------------------

    def broadcast(self, message, exclude_session=None):
        payload_skip = exclude_session
        for session in self.all_sessions():
            if payload_skip is not None and session is payload_skip:
                continue
            session.send(message)

    def broadcast_roster(self):
        with self.lock:
            message = self.build_roster_message()
        if message is not None:
            self.broadcast(message)

    def build_roster_message(self):
        """调用方须已持有 lock。"""
        return build_roster(
            phase=self.room.phase,
            round_id=self.room.round_id,
            state_revision=self.room.state_revision,
            map_name=self.room.map_name,
            players=self.room.roster_players(),
            host_player_id=self.room.host_player_id,
            team_size=self.room.team_size,
        )

    @staticmethod
    def _now_ms():
        return int(time.time() * 1000)


class ClientHandler(socketserver.BaseRequestHandler):
    """单连接：hello 握手 → 循环读消息。"""

    HANDSHAKE_TIMEOUT = 10.0
    IDLE_TIMEOUT = 60.0
    RECV_SIZE = 4096

    def handle(self):
        server = self.server.game_server
        conn = self.request
        try:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        conn.settimeout(self.HANDSHAKE_TIMEOUT)
        decoder = LineDecoder()
        self._pending = []
        session = None
        try:
            # --- 收首条 hello ---
            hello = self._read_one(decoder, conn)
            if hello is None:
                return
            kind = message_type_of(hello)
            if kind != MSG_HELLO:
                self._send_raw(conn, build_error(
                    ERROR_INVALID_HELLO, 'first message must be hello',
                    close=True))
                return

            session, error = server.accept_hello(hello, conn, self.client_address)
            if session is None:
                self._send_raw(conn, build_error(
                    error[0], error[1], close=True))
                return

            welcome = server.build_welcome(session)
            if not session.send(welcome):
                server.detach_session(session)
                return

            # 先给新玩家本人 roster，再通知其他人
            with server.world.lock:
                roster_msg = server.world.build_roster_message()
            if roster_msg is not None:
                session.send(roster_msg)
            server.broadcast_roster(exclude_session=session)

            # --- 已读残余字节 + 持续读 ---
            conn.settimeout(self.IDLE_TIMEOUT)
            leftover = self._drain_pending(decoder, conn)
            for message in leftover:
                if not server.dispatch_message(session, message):
                    break
            else:
                while session.connected:
                    try:
                        chunk = conn.recv(self.RECV_SIZE)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    if not chunk:
                        break
                    messages = decoder.feed(chunk)
                    if decoder.overflow:
                        session.send(build_error(
                            'buffer_overflow', 'receive buffer exceeded',
                            close=True))
                        break
                    for message in messages:
                        if not server.dispatch_message(session, message):
                            session.connected = False
                            break
                    if not session.connected:
                        break
                # flush 半行
                for message in decoder.flush():
                    if not server.dispatch_message(session, message):
                        break
        except (ProtocolError, ValueError) as exc:
            self._send_raw(conn, build_error(
                ERROR_INVALID_HELLO, str(exc), close=True))
        finally:
            if session is not None:
                server.detach_session(session)
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass

    def _read_one(self, decoder, conn):
        while True:
            try:
                chunk = conn.recv(self.RECV_SIZE)
            except socket.timeout:
                return None
            except OSError:
                return None
            if not chunk:
                return None
            messages = decoder.feed(chunk)
            if decoder.overflow:
                return None
            if messages:
                # 若缓冲里还有后续行，服务器侧在 session 绑定后自行 drain
                self._pending = messages[1:]
                return messages[0]

    def _drain_pending(self, decoder, conn):
        pending = getattr(self, '_pending', None) or []
        return list(pending)

    @staticmethod
    def _send_raw(conn, message):
        try:
            conn.sendall(encode_message(message))
        except OSError:
            pass


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class GameServer(object):
    """组装 GameWorld + TCP server + TickLoop。"""

    def __init__(self, host=DEFAULT_SERVER_HOST, port=DEFAULT_SERVER_PORT,
                 map_name='vvg_default', team_size=15,
                 server_tick_hz=30.0, snapshot_hz=15.0,
                 world_capabilities=None):
        self.host = host
        self.port = int(port)
        self.map_name = map_name
        self.world = GameWorld(
            map_name=map_name,
            team_size=team_size,
            server_capabilities=world_capabilities,
        )
        self.tick_hz = float(server_tick_hz)
        self.snapshot_hz = float(snapshot_hz) if snapshot_hz else None
        self.tick_loop = TickLoop(
            self.world,
            tick_hz=self.tick_hz,
            snapshot_hz=self.snapshot_hz,
        )
        self._tcp = None
        self._tick_thread = None
        self._bound_port = None

    # --- 生命周期 -----------------------------------------------------------

    def start(self, background=True):
        """绑定端口并启动 tick；background=True 时后台线程 serve_forever。"""
        self._tcp = ThreadedTCPServer((self.host, self.port), ClientHandler)
        self._tcp.game_server = self
        self._bound_port = self._tcp.server_address[1]
        if background:
            server_thread = threading.Thread(
                target=self._tcp.serve_forever,
                kwargs={'poll_interval': 0.2},
                name='vvg-tcp',
                daemon=True)
            server_thread.start()
            self._tcp._serve_thread = server_thread
        if background:
            self._tick_thread = threading.Thread(
                target=self.tick_loop.run,
                kwargs={'shutdown_callback': self.stop},
                name='vvg-tick',
                daemon=True)
            self._tick_thread.start()
        return self

    def serve_forever(self):
        """前台 TCP + 后台 tick。"""
        self.start(background=True)
        try:
            self._tcp.serve_forever(poll_interval=0.2)
        finally:
            self.stop()

    def stop(self):
        self.world.running = False
        tcp = self._tcp
        self._tcp = None
        if tcp is not None:
            try:
                tcp.shutdown()
            except Exception:
                pass
            try:
                tcp.server_close()
            except Exception:
                pass

    @property
    def bound_port(self):
        return self._bound_port

    def run_ticks(self, count, dt=None):
        """测试辅助：手动推进 n 个 tick（不经 sleep）。"""
        step = dt if dt is not None else 1.0 / self.tick_hz
        for _ in range(int(count)):
            if not self.world.running:
                break
            self.world.tick_once(step, self.tick_loop.server_tick)
            self.tick_loop.server_tick += 1
            if self.tick_loop.snapshot_ticks is not None:
                tick = self.tick_loop.server_tick
                if tick > 0 and tick % self.tick_loop.snapshot_ticks == 0:
                    self.world.broadcast_snapshot(tick)

    # --- 握手 ---------------------------------------------------------------

    def accept_hello(self, hello, conn, client_address):
        """校验 hello 并加入房间。

        返回 (session, None) 或 (None, (code, message))。
        """
        if hello.get('protocol') != PROTOCOL_VERSION:
            return None, (ERROR_PROTOCOL_MISMATCH, 'protocol mismatch')

        role = hello.get('role') or ROLE_PLAYER
        if role != ROLE_PLAYER:
            return None, (ERROR_UNSUPPORTED_ROLE, 'unsupported role')

        try:
            negotiation = negotiate(
                hello.get('capabilities'), self.world.server_capabilities)
        except Exception as exc:
            return None, (ERROR_UNSUPPORTED_CAPABILITIES, str(exc))
        if not negotiation['ok']:
            return None, (
                ERROR_UNSUPPORTED_CAPABILITIES,
                'missing required capabilities',
            )

        name = hello.get('name')
        vehicle = hello.get('vehicle')
        if not name or not vehicle:
            return None, (ERROR_INVALID_HELLO, 'player hello requires name and vehicle')

        requested = hello.get('requested_team') or 0
        try:
            requested = int(requested)
        except (TypeError, ValueError):
            requested = 0

        with self.world.lock:
            try:
                session = self.world.room.join(
                    name=name,
                    vehicle=vehicle,
                    capabilities=negotiation['shared'],
                    client_build=hello.get('client_build'),
                    requested_team=requested,
                    max_health=hello.get('max_health'),
                    account_key=hello.get('account_key'),
                    peer=client_address,
                )
            except ValueError as exc:
                return None, (ERROR_JOIN_REJECTED, str(exc))

            session.bind_send(self._make_sender(conn))
            self.world.register_session(session)
        return session, None

    def build_welcome(self, session):
        with self.world.lock:
            room = self.world.room
            fields = room.welcome_fields(session)
            return build_welcome(
                player_id=session.player_id,
                name=session.name,
                vehicle=session.vehicle,
                team=session.team,
                map_name=fields['map'],
                phase=fields['phase'],
                round_id=fields['round_id'],
                state_revision=fields['state_revision'],
                host_player_id=fields['host_player_id'],
                capabilities=session.capabilities,
                server_capabilities=self.world.server_capabilities,
                client_build=session.client_build,
                server_time_ms=self.world.server_time_ms(),
                spawn=fields['spawn'],
            )

    def broadcast_roster(self, exclude_session=None):
        with self.world.lock:
            message = self.world.build_roster_message()
        if message is not None:
            self.world.broadcast(message, exclude_session=exclude_session)

    def detach_session(self, session):
        session.mark_disconnected()
        self.world.unregister_session(session)
        self.broadcast_roster()

    # --- 消息分发 -----------------------------------------------------------

    def dispatch_message(self, session, message):
        """处理一条已解码消息。返回 False 表示应关闭连接。"""
        kind = message_type_of(message)
        if kind is None:
            return True
        if kind == MSG_PING:
            return session.send(build_pong(
                message.get('seq', 0),
                client_time=message.get('client_time'),
                server_time=time.time(),
            ))
        if kind == MSG_LEAVE:
            session.connected = False
            return False
        if kind == MSG_LEAVE_BATTLE:
            return self._handle_leave_battle(session, message)
        if kind == MSG_START_BATTLE:
            return self._handle_start_battle(session, message)
        if kind == MSG_SELECT_TEAM:
            return self._handle_select_team(session, message)
        if kind == MSG_SELECT_VEHICLE:
            return self._handle_select_vehicle(session, message)
        if kind == MSG_BATTLE_READY:
            return self._handle_battle_ready(session, message)
        if kind == MSG_INPUT:
            return self._handle_input(session, message)
        return True

    def _handle_leave_battle(self, session, message):
        with self.world.lock:
            room = self.world.room
            if (room.phase == PHASE_BATTLE
                    and message.get('round_id') == room.round_id):
                room.return_to_waiting()
        self.broadcast_roster()
        return True

    def _handle_start_battle(self, session, message):
        with self.world.lock:
            room = self.world.room
            requested_round_seconds = message.get('round_seconds')
            ok, result = room.try_start_battle(
                session.player_id,
                round_seconds=requested_round_seconds,
            )
            if not ok:
                denied = build_start_denied(result, result)
                events = None
            else:
                start = result['battle_start']
                live = result['battle_live']
                events = {'battle_start': start, 'battle_live': live}
                denied = None
        if not ok:
            session.send(denied)
            return True
        # 屏障消息按序广播给全员
        self.world.broadcast(events['battle_start'])
        self.world.broadcast(events['battle_live'])
        self.broadcast_roster()
        return True

    def _handle_select_team(self, session, message):
        team = message.get('team')
        try:
            team = int(team)
        except (TypeError, ValueError):
            team = 0
        with self.world.lock:
            if team == 0:
                # auto：按当前人数重新分
                from sim_worker.room.lobby import assign_team
                try:
                    others = [
                        p for p in self.world.room.players()
                        if p.player_id != session.player_id
                    ]
                    session.team = assign_team(
                        0, others, team_size=self.world.room.team_size)
                    self.world.room._bump_revision()
                    ok, reason = True, ''
                except ValueError:
                    ok, reason = False, 'team_full'
            else:
                ok, reason = self.world.room.set_team(session.player_id, team)
        if not ok:
            session.send(build_team_denied(team, reason))
        else:
            self.broadcast_roster()
        return True

    def _handle_select_vehicle(self, session, message):
        vehicle = message.get('vehicle')
        if not vehicle:
            return True
        with self.world.lock:
            self.world.room.set_vehicle(
                session.player_id,
                vehicle,
                max_health=message.get('max_health'),
            )
        self.broadcast_roster()
        return True

    def _handle_battle_ready(self, session, message):
        with self.world.lock:
            self.world.room.mark_ready(
                session.player_id, message.get('round_id', 0))
        self.broadcast_roster()
        return True

    def _handle_input(self, session, message):
        with self.world.lock:
            self.world.room.apply_input(session.player_id, message)
        return True

    @staticmethod
    def _make_sender(conn):
        def send(message):
            try:
                conn.sendall(encode_message(message))
                return True
            except OSError:
                return False
        return send


__all__ = [
    'GameServer',
    'GameWorld',
    'ClientHandler',
    'ThreadedTCPServer',
]
