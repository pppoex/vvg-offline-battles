# -*- coding: utf-8 -*-
"""sim-worker 入口 — 命令行启动权威服务器。

用法::

    python -m sim_worker.main --host 127.0.0.1 --port 28782 --map training
"""
from __future__ import absolute_import, division, print_function

import argparse
import signal
import sys
import threading

from protocol.constants import (
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
    PROTOCOL_VERSION,
)
from sim_worker.server import GameServer


def build_parser():
    parser = argparse.ArgumentParser(
        prog='sim_worker',
        description='vvg-offline-battles authoritative sim server')
    parser.add_argument(
        '--host', default=DEFAULT_SERVER_HOST,
        help='bind address (default: %s)' % DEFAULT_SERVER_HOST)
    parser.add_argument(
        '--port', type=int, default=DEFAULT_SERVER_PORT,
        help='TCP port (default: %d)' % DEFAULT_SERVER_PORT)
    parser.add_argument(
        '--map', default='vvg_default', dest='map_name',
        help='room map name')
    parser.add_argument(
        '--team-size', type=int, default=15,
        help='max players per team')
    parser.add_argument(
        '--tick-hz', type=float, default=30.0,
        help='world tick rate')
    parser.add_argument(
        '--snapshot-hz', type=float, default=15.0,
        help='snapshot broadcast rate')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    server = GameServer(
        host=args.host,
        port=args.port,
        map_name=args.map_name,
        team_size=args.team_size,
        server_tick_hz=args.tick_hz,
        snapshot_hz=args.snapshot_hz,
    )
    stop_event = threading.Event()

    def _handle_signal(signum, frame):
        print('[sim-worker] signal %s, shutting down' % signum)
        stop_event.set()
        server.stop()

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except (ValueError, OSError):
        # 非主线程 / 平台差异
        pass

    print('[sim-worker] protocol=%d listen=%s:%d map=%s tick=%.1fHz snap=%.1fHz'
          % (PROTOCOL_VERSION, server.host, args.port, args.map_name,
             server.tick_hz, server.snapshot_hz or 0.0))
    # start 在绑定后填充 bound_port（port=0 时有用）
    server.start(background=True)
    if server.bound_port != args.port:
        print('[sim-worker] bound port=%d' % server.bound_port)
    print('[sim-worker] ready')
    try:
        # 前台等待直到 stop
        while server.world.running and not stop_event.is_set():
            stop_event.wait(0.5)
    finally:
        server.stop()
    print('[sim-worker] stopped')
    return 0


if __name__ == '__main__':
    sys.exit(main())
