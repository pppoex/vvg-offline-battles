# -*- coding: utf-8 -*-
"""Deploy the multi-client guard into a WoT 2.3.1.2 install.

Installs (never touches game exe/dll/pkg):

  res_mods/2.3.1.2/scripts/client/gui/mods/
      mod_vvg_instance_guard.py
      vvg_instance_guard/
          __init__.py
          bootstrap.py
          instance_guard.py          (copied from src/multiclient)

  mods/2.3.1.2/
      vvg_instance_guard_native.pyd

  win64/                              (optional convenience copies)
      vvg_instance_guard_native.pyd
      vvg_worker_starter.exe

Usage (from workspace root, any Python 2.7+ or 3):

  python src/deploy/install_multiclient.py
  python src/deploy/install_multiclient.py --game-root "D:\\WOT\\World_of_Tanks_EU_Offline_2.3.1.2"
"""
from __future__ import print_function

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CLIENT_SRC = os.path.join(ROOT, 'src', 'client')
MULTICLIENT_SRC = os.path.join(ROOT, 'src', 'multiclient')
DIST = os.path.join(ROOT, 'dist', 'multiclient')

DEFAULT_GAME_ROOT = os.path.normpath(
    r'D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2')

GAME_VERSION = '2.3.1.2'
MOD_ENTRY = 'mod_vvg_instance_guard.py'
PACKAGE_DIR = 'vvg_instance_guard'
NATIVE_NAME = 'vvg_instance_guard_native.pyd'
STARTER_NAME = 'vvg_worker_starter.exe'

# Independent names — never collide with Offline2.3.1.2 / offhangar2 / openwg.
RES_MODS_REL = os.path.join(
    'res_mods', GAME_VERSION, 'scripts', 'client', 'gui', 'mods')
MODS_REL = os.path.join('mods', GAME_VERSION)


def _log(message):
    sys.stdout.write('[install_multiclient] %s\n' % message)
    sys.stdout.flush()


def _require_file(path, what):
    if not os.path.isfile(path):
        raise SystemExit('missing %s: %s' % (what, path))
    return path


def _copy_file(src, dst, label):
    parent = os.path.dirname(dst)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    shutil.copy2(src, dst)
    _log('installed %s -> %s' % (label, dst))


def install(game_root, dry_run=False):
    game_root = os.path.abspath(game_root)
    if not os.path.isdir(game_root):
        raise SystemExit('game root not found: %s' % game_root)
    if not os.path.isfile(os.path.join(game_root, 'win64', 'WorldOfTanks.exe')):
        _log('warning: win64/WorldOfTanks.exe not found under %s '
             '(continuing anyway)' % game_root)

    # --- source artefacts ---
    entry_src = _require_file(
        os.path.join(CLIENT_SRC, MOD_ENTRY), 'mod entry')
    init_src = _require_file(
        os.path.join(CLIENT_SRC, PACKAGE_DIR, '__init__.py'), 'package init')
    bootstrap_src = _require_file(
        os.path.join(CLIENT_SRC, PACKAGE_DIR, 'bootstrap.py'), 'bootstrap')
    guard_src = _require_file(
        os.path.join(MULTICLIENT_SRC, 'instance_guard.py'), 'instance_guard')

    native_src = None
    for candidate in (
            os.path.join(DIST, NATIVE_NAME),
            os.path.join(MULTICLIENT_SRC, 'native', 'out', NATIVE_NAME),
            os.path.join(game_root, 'win64', NATIVE_NAME),
            os.path.join(game_root, MODS_REL, NATIVE_NAME),
    ):
        if os.path.isfile(candidate):
            native_src = candidate
            break
    starter_src = None
    for candidate in (
            os.path.join(DIST, STARTER_NAME),
            os.path.join(MULTICLIENT_SRC, 'native', 'out', STARTER_NAME),
            os.path.join(game_root, 'win64', STARTER_NAME),
    ):
        if os.path.isfile(candidate):
            starter_src = candidate
            break

    # --- destinations ---
    mods_dest = os.path.join(game_root, RES_MODS_REL)
    pkg_dest = os.path.join(mods_dest, PACKAGE_DIR)
    native_mods_dest = os.path.join(game_root, MODS_REL, NATIVE_NAME)
    native_win64_dest = os.path.join(game_root, 'win64', NATIVE_NAME)
    starter_dest = os.path.join(game_root, 'win64', STARTER_NAME)

    planned = [
        (entry_src, os.path.join(mods_dest, MOD_ENTRY), 'mod entry'),
        (init_src, os.path.join(pkg_dest, '__init__.py'), 'package init'),
        (bootstrap_src, os.path.join(pkg_dest, 'bootstrap.py'), 'bootstrap'),
        (guard_src, os.path.join(pkg_dest, 'instance_guard.py'),
         'instance_guard'),
    ]
    if native_src:
        planned.append((native_src, native_mods_dest, 'native pyd (mods)'))
        planned.append((native_src, native_win64_dest, 'native pyd (win64)'))
    if starter_src:
        planned.append((starter_src, starter_dest, 'worker starter'))

    if dry_run:
        for src, dst, label in planned:
            _log('would install %s -> %s' % (label, dst))
        return planned

    for src, dst, label in planned:
        _copy_file(src, dst, label)

    if native_src is None:
        _log('WARNING: native pyd not found in dist/ — build with '
             'src/multiclient/native/build.ps1 then re-run this script')
    else:
        _log('native bridge source: %s' % native_src)

    _log('done. Start clients with vvg_worker_starter.exe '
         '(sets VVG_ALLOW_MULTIPLE_CLIENTS=1 and VVG_INSTANCE_GUARD_PATH).')
    _log('First client must reach GUI (mod init) before launching the second, '
         'so WOT_STARTUP_MUTEX is already released.')
    return planned


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Install VVG multi-client guard into a WoT install')
    parser.add_argument(
        '--game-root', default=DEFAULT_GAME_ROOT,
        help='game install root (default: %s)' % DEFAULT_GAME_ROOT)
    parser.add_argument(
        '--dry-run', action='store_true',
        help='print planned copies without writing')
    args = parser.parse_args(argv)
    install(args.game_root, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())
