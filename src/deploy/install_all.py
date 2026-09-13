# -*- coding: utf-8 -*-
"""Install all VVG client-side pieces into a game install (thin shell).

Runs, in order (each is optional via --skip / --only):

  1. install_multiclient  — instance guard + vvg_worker_starter.exe
  2. install_client       — thin client mod (network / prediction)
  3. install_offhangar    — Offline hangar so the client reaches the garage

Never touches game exe/dll/pkg; only writes under res_mods/ + win64 copies
that the existing scripts already allow.

Usage (workspace root):

  python src/deploy/install_all.py
  python -m launcher deploy
"""
from __future__ import print_function

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

DEFAULT_GAME_ROOT = os.path.normpath(
    r'D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2')

ORDER = ('multiclient', 'client', 'offhangar')


def _log(message):
    sys.stdout.write('[install_all] %s\n' % message)
    sys.stdout.flush()


def _load_modules():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import install_multiclient  # noqa: E402
    import install_client  # noqa: E402
    import install_offhangar  # noqa: E402
    return install_multiclient, install_client, install_offhangar


def select_components(only=None, skip=None):
    if only and skip:
        raise SystemExit('pass only one of --only / --skip')
    names = list(ORDER)
    if only:
        if only not in ORDER:
            raise SystemExit('unknown component %r (choose from %s)'
                             % (only, ', '.join(ORDER)))
        names = [only]
    if skip:
        if skip not in ORDER:
            raise SystemExit('unknown component %r (choose from %s)'
                             % (skip, ', '.join(ORDER)))
        names = [n for n in names if n != skip]
    return names


def install_all(game_root=None, python27=None, only=None, skip=None,
                skip_sdk=False, dry_run=False):
    """Run the selected installers. Returns 0 on success, non-zero otherwise."""
    game_root = os.path.normpath(game_root or DEFAULT_GAME_ROOT)
    if not dry_run and not os.path.isdir(game_root):
        _log('ERROR: game root not found: %s' % game_root)
        return 1

    multiclient, client, offhangar = _load_modules()
    selected = select_components(only=only, skip=skip)
    _log('game_root=%s components=%s' % (game_root, ','.join(selected)))
    if dry_run:
        _log('dry-run: no files will be written')

    results = {}

    if 'multiclient' in selected:
        _log('--- install_multiclient ---')
        try:
            multiclient.install(
                game_root, dry_run=dry_run, python27=python27)
            results['multiclient'] = 0
        except SystemExit as exc:
            _log('multiclient FAILED: %s' % exc)
            results['multiclient'] = 1

    if 'client' in selected:
        _log('--- install_client ---')
        try:
            code = client.install(
                game_root,
                python27=python27,
                skip_sdk=skip_sdk,
                dry_run=dry_run,
            )
            results['client'] = int(code or 0)
        except SystemExit as exc:
            _log('client FAILED: %s' % exc)
            results['client'] = 1

    if 'offhangar' in selected:
        _log('--- install_offhangar ---')
        try:
            # install_offhangar has no dry_run flag; skip on dry-run.
            if dry_run:
                _log('dry-run: would install offhangar2 into res_mods')
                results['offhangar'] = 0
            else:
                code = offhangar.install(game_root, python27=python27)
                results['offhangar'] = int(code or 0)
        except SystemExit as exc:
            _log('offhangar FAILED: %s' % exc)
            results['offhangar'] = 1

    failed = [k for k, v in results.items() if v != 0]
    for name in selected:
        _log('component %s -> %s' % (name, results.get(name)))
    if failed:
        _log('FAILED: %s' % ', '.join(failed))
        return 1
    _log('all selected components installed')
    _log('start with: python -m launcher server | player | worker')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Install multiclient + thin client + offhangar into a '
                    'WoT 2.3.1.2 install')
    parser.add_argument(
        '--game-root', default=DEFAULT_GAME_ROOT,
        help='game install root (default: %s)' % DEFAULT_GAME_ROOT)
    parser.add_argument('--python27', default=None)
    parser.add_argument(
        '--only', choices=list(ORDER), help='install only one component')
    parser.add_argument(
        '--skip', choices=list(ORDER), help='skip one component')
    parser.add_argument(
        '--skip-sdk', action='store_true', help='client: skip sdk copy')
    parser.add_argument(
        '--dry-run', action='store_true', help='print plan, write nothing')
    args = parser.parse_args(argv)
    return install_all(
        game_root=args.game_root,
        python27=args.python27,
        only=args.only,
        skip=args.skip,
        skip_sdk=args.skip_sdk,
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    sys.exit(main())
