# -*- coding: utf-8 -*-
"""python -m launcher — thin CLI over deploy / sim-worker / game clients."""
from __future__ import absolute_import, division, print_function

import argparse
import os
import sys

from launcher import client as clientmod
from launcher import env as envmod
from launcher import paths as pathmod
from launcher import ports
from launcher import server as servermod


def _import_install_all():
    deploy_pkg = os.path.join(
        pathmod.workspace_root(), 'src', 'deploy')
    if deploy_pkg not in sys.path:
        sys.path.insert(0, deploy_pkg)
    import install_all  # noqa: E402
    return install_all


def _add_server_args(parser):
    parser.add_argument(
        '--host', default=envmod.DEFAULT_SERVER_HOST,
        help='bind address (default: %s)' % envmod.DEFAULT_SERVER_HOST)
    parser.add_argument(
        '--port', type=int, default=envmod.DEFAULT_SERVER_PORT,
        help='TCP port (default: %d)' % envmod.DEFAULT_SERVER_PORT)
    parser.add_argument(
        '--map', default=None, dest='map_name', help='room map name')
    parser.add_argument(
        '--kill-port', action='store_true',
        help='if the port is already in use, kill the local listener first')
    parser.add_argument(
        '--ready-timeout', type=float, default=15.0,
        help='seconds to wait for sim-worker to bind (default: 15)')


def _add_client_common(parser):
    parser.add_argument(
        '--host', default=envmod.DEFAULT_SERVER_HOST,
        help='sim-worker host (default: %s)' % envmod.DEFAULT_SERVER_HOST)
    parser.add_argument(
        '--port', type=int, default=envmod.DEFAULT_SERVER_PORT,
        help='sim-worker port (default: %d)' % envmod.DEFAULT_SERVER_PORT)
    parser.add_argument(
        '--game-root', default=None,
        help='game install root (default: $VVG_GAME_ROOT or %s)'
             % pathmod.DEFAULT_GAME_ROOT)
    parser.add_argument(
        '--workspace', default=None,
        help='workspace root containing src/ (default: auto-detect)')
    parser.add_argument(
        '--force-game-exe', action='store_true',
        help='bypass vvg_worker_starter.exe and launch WorldOfTanks.exe')


def build_parser():
    parser = argparse.ArgumentParser(
        prog='launcher',
        description='vvg-offline-battles command-line launcher '
                    '(deploy / sim-worker / player / worker)')
    sub = parser.add_subparsers(dest='command')

    p_deploy = sub.add_parser(
        'deploy', help='install multiclient + thin client + offhangar')
    p_deploy.add_argument(
        '--game-root', default=None,
        help='game install root (default: $VVG_GAME_ROOT or %s)'
             % pathmod.DEFAULT_GAME_ROOT)
    p_deploy.add_argument('--python27', default=None)
    p_deploy.add_argument(
        '--only', choices=('multiclient', 'client', 'offhangar'),
        help='install only one component')
    p_deploy.add_argument(
        '--skip', choices=('multiclient', 'client', 'offhangar'),
        help='skip one component')
    p_deploy.add_argument(
        '--skip-sdk', action='store_true', help='client install: skip sdk copy')
    p_deploy.add_argument(
        '--dry-run', action='store_true', help='print plan, write nothing')

    p_server = sub.add_parser(
        'server', help='run authoritative sim-worker (foreground)')
    _add_server_args(p_server)

    p_player = sub.add_parser(
        'player', help='start one player game client')
    _add_client_common(p_player)
    p_player.add_argument(
        '--name', default=None, help='player name (VVG_PLAYER_NAME)')
    p_player.add_argument(
        '--vehicle', default=None,
        help='vehicle compact descr (VVG_PLAYER_VEHICLE)')

    p_worker = sub.add_parser(
        'worker', help='start one simulation_worker game client')
    _add_client_common(p_worker)
    win = p_worker.add_mutually_exclusive_group()
    win.add_argument(
        '--show', dest='show', action='store_true', default=None,
        help='visible worker window (debug)')
    win.add_argument(
        '--hide', dest='show', action='store_false',
        help='hidden desktop worker (starter default)')

    return parser


def cmd_deploy(args):
    install_all = _import_install_all()
    game_root = pathmod.game_root(args.game_root)
    return install_all.install_all(
        game_root,
        python27=args.python27,
        only=args.only,
        skip=args.skip,
        skip_sdk=args.skip_sdk,
        dry_run=args.dry_run,
    )


def cmd_server(args):
    workspace = pathmod.workspace_root()
    return servermod.run_server(
        host=args.host,
        port=args.port,
        map_name=args.map_name,
        kill_port=args.kill_port,
        ready_timeout=args.ready_timeout,
        workspace=workspace,
    )


def cmd_player(args):
    proc, kind, _path = clientmod.start_client(
        role='player',
        name=args.name,
        vehicle=args.vehicle,
        host=args.host,
        port=args.port,
        root=args.game_root,
        workspace=args.workspace,
        force_fallback=args.force_game_exe,
    )
    # Detach: launcher exits; the game keeps running.
    try:
        proc.poll()
    except Exception:
        pass
    ports.log('player launched (pid=%s, %s); launcher exiting'
              % (proc.pid, kind))
    return 0


def cmd_worker(args):
    proc, kind, _path = clientmod.start_client(
        role='worker',
        host=args.host,
        port=args.port,
        show=args.show,
        root=args.game_root,
        workspace=args.workspace,
        force_fallback=args.force_game_exe,
    )
    ports.log('worker launched (pid=%s, %s); launcher exiting'
              % (proc.pid, kind))
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, 'command', None):
        parser.print_help()
        return 1
    if args.command == 'deploy':
        return cmd_deploy(args)
    if args.command == 'server':
        return cmd_server(args)
    if args.command == 'player':
        return cmd_player(args)
    if args.command == 'worker':
        return cmd_worker(args)
    parser.error('unknown command %r' % args.command)
    return 1


if __name__ == '__main__':
    sys.exit(main())
