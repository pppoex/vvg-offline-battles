# -*- coding: utf-8 -*-
"""TCP transport — socket + LineDecoder + thread-safe send/recv queues.

Python 2/3 dual-compatible. Reuses ``protocol.serializer.LineDecoder``.
"""
from __future__ import absolute_import, division, print_function

import socket
import threading
import time

from protocol.constants import MAX_BUFFER_BYTES
from protocol.serializer import LineDecoder, encode_message

# Inbound messages queued for the main-thread pump. Ordered state barriers
# are never dropped; excess snapshots are shed oldest-first.
MAX_PENDING_MESSAGES = 512
MAX_PENDING_BYTES = MAX_BUFFER_BYTES
SOCKET_RECV_TIMEOUT = 0.25
CONNECT_TIMEOUT = 3.0


def monotonic_time():
    """Process clock that does not jump (Py2.7-safe)."""
    function = getattr(time, 'monotonic', None)
    if callable(function):
        return float(function())
    # Python 2.7 on Windows: time.clock() is QueryPerformanceCounter.
    return float(time.clock())  # noqa: F821  (Py2 only path)


class ConnectionErrorState(Exception):
    """Raised when a send/connect fails in a fatal way."""


class TcpLineConnection(object):
    """One live TCP session carrying JSON lines frames.

    - Background thread owns recv / decode / queue push.
    - ``send_message`` is thread-safe (send lock).
    - ``poll`` drains inbound messages for the owner (main / test thread).
    """

    def __init__(self, host, port, name='vvg-client'):
        self.host = str(host)
        self.port = int(port)
        self.name = name
        self._sock = None
        self._decoder = LineDecoder()
        self._pending = []
        self._pending_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._recv_thread = None
        self._stopping = False
        self._connected = False
        self._error = None
        self._generation = 0

    # --- 状态 ---------------------------------------------------------------

    @property
    def connected(self):
        return bool(self._connected)

    @property
    def last_error(self):
        return self._error

    # --- 连接生命周期 -------------------------------------------------------

    def open(self, timeout=CONNECT_TIMEOUT):
        """Connect the socket. Does not send any protocol message yet."""
        if self._connected:
            return True
        self._error = None
        self._stopping = False
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(float(timeout))
        try:
            sock.connect((self.host, self.port))
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except Exception:
                pass
            sock.settimeout(SOCKET_RECV_TIMEOUT)
        except Exception as exc:
            try:
                sock.close()
            except Exception:
                pass
            self._error = str(exc)
            return False

        self._generation += 1
        generation = self._generation
        self._sock = sock
        self._decoder.reset()
        with self._pending_lock:
            self._pending = []
        self._connected = True

        thread = threading.Thread(
            target=self._recv_loop,
            args=(sock, generation),
            name='%s-recv' % self.name)
        try:
            thread.daemon = True
        except Exception:
            pass
        self._recv_thread = thread
        thread.start()
        return True

    def close(self, send_leave=False, leave_message=None):
        """Stop the recv thread and close the socket."""
        self._stopping = True
        sock = self._sock
        if send_leave and sock is not None and leave_message is not None:
            try:
                payload = encode_message(leave_message)
                sock.sendall(payload)
            except Exception:
                pass
        self._generation += 1
        self._connected = False
        self._sock = None
        try:
            if sock is not None:
                sock.close()
        except Exception:
            pass
        thread = self._recv_thread
        self._recv_thread = None
        if thread is not None and thread.is_alive():
            try:
                thread.join(0.5)
            except Exception:
                pass
        return True

    # --- 发送 ---------------------------------------------------------------

    def send_message(self, message):
        """Encode and send one dict. Returns True on success."""
        sock = self._sock
        if sock is None or not self._connected or self._stopping:
            return False
        try:
            payload = encode_message(message)
        except Exception as exc:
            self._error = str(exc)
            return False
        try:
            with self._send_lock:
                sock.sendall(payload)
            return True
        except Exception as exc:
            self._error = str(exc)
            self._connected = False
            return False

    # --- 接收 / pump --------------------------------------------------------

    def poll(self, max_messages=64):
        """Drain up to ``max_messages`` inbound frames for the owner."""
        out = []
        with self._pending_lock:
            while self._pending and len(out) < int(max_messages):
                out.append(self._pending.pop(0))
        return out

    def pending_count(self):
        with self._pending_lock:
            return len(self._pending)

    # --- 内部 ---------------------------------------------------------------

    def _recv_loop(self, sock, generation):
        try:
            while (not self._stopping
                   and generation == self._generation
                   and self._sock is sock):
                try:
                    chunk = sock.recv(8192)
                except socket.timeout:
                    continue
                except Exception as exc:
                    if not self._stopping:
                        self._error = str(exc)
                    break
                if generation != self._generation or self._sock is not sock:
                    break
                if not chunk:
                    if not self._stopping:
                        self._error = 'server closed the connection'
                    break
                try:
                    messages = self._decoder.feed(chunk)
                except Exception as exc:
                    self._error = str(exc)
                    break
                if self._decoder.overflow:
                    self._error = 'receive buffer overflow'
                    break
                for message in messages:
                    self._enqueue(message, generation)
        finally:
            if generation == self._generation and self._sock is sock:
                self._connected = False

    def _enqueue(self, message, generation):
        with self._pending_lock:
            if generation != self._generation or self._stopping:
                return
            if len(self._pending) >= MAX_PENDING_MESSAGES:
                # Shed oldest non-barrier frames first (snapshot backlog).
                removable = None
                for index, value in enumerate(self._pending):
                    if value.get('type') not in (
                            'welcome', 'roster', 'battle_start',
                            'battle_live', 'start_denied', 'team_denied',
                            'events', 'error', 'pong'):
                        removable = index
                        break
                if removable is not None:
                    del self._pending[removable]
                elif message.get('type') not in (
                        'welcome', 'roster', 'battle_start', 'battle_live',
                        'start_denied', 'team_denied', 'events', 'error',
                        'pong'):
                    return
            self._pending.append(message)


__all__ = [
    'TcpLineConnection',
    'ConnectionErrorState',
    'monotonic_time',
    'MAX_PENDING_MESSAGES',
]
