# -*- coding: utf-8 -*-
"""Deploy Offline2.3.1.2 hangar mod (mod_offhangar2) into the game install.

Provides the offline fake-server / auto-login path so the client can enter
the hangar. Source stays read-only; only copies into the game res_mods tree.

Does NOT overwrite vvg thin-client / instance-guard packages.

Usage:
  python src/deploy/install_offhangar.py
  python src/deploy/install_offhangar.py --game-root "D:\\WOT\\..."
"""
from __future__ import print_function

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))

# Read-only Offline source (never write here) — package body
OFFLINE_MOD_SRC = os.path.normpath(
    r'D:\Projects\Offline2.3.1.2\script\client\gui\mods')

# Fixed entry (cleans Decompyle++ UnboundLocalError in init/fini)
FIXED_ENTRY = os.path.join(
    ROOT, 'src', 'client', 'offline_entry', 'mod_offhangar2.py')

DEFAULT_GAME_ROOT = os.path.normpath(
    r'D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2')

GAME_VERSION = '2.3.1.2'
MOD_ENTRY = 'mod_offhangar2.py'
PACKAGE_DIR = 'offhangar2'
RES_MODS_REL = os.path.join(
    'res_mods', GAME_VERSION, 'scripts', 'client', 'gui', 'mods')


def _log(message):
    sys.stdout.write('[install_offhangar] %s\n' % message)
    sys.stdout.flush()


def _iter_python_files(root):
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith('.py'):
                yield os.path.join(dirpath, name)


def install(game_root, python27=None):
    game_root = os.path.normpath(game_root)
    mods_dir = os.path.join(game_root, RES_MODS_REL)

    entry_src = FIXED_ENTRY
    if not os.path.isfile(entry_src):
        # Fallback only if workspace entry is missing
        entry_src = os.path.join(OFFLINE_MOD_SRC, MOD_ENTRY)
        _log('WARNING: using unfixed Offline entry (decompyle artifact)')
    pkg_src = os.path.join(OFFLINE_MOD_SRC, PACKAGE_DIR)
    if not os.path.isfile(entry_src):
        raise SystemExit('missing Offline mod entry: %s' % entry_src)
    if not os.path.isdir(pkg_src):
        raise SystemExit('missing Offline package: %s' % pkg_src)

    if not os.path.isdir(mods_dir):
        os.makedirs(mods_dir)

    # Replace Offline package only (leave vvg_* / protocol / sdk alone).
    dst_pkg = os.path.join(mods_dir, PACKAGE_DIR)
    if os.path.isdir(dst_pkg):
        shutil.rmtree(dst_pkg)
    shutil.copytree(pkg_src, dst_pkg)
    _log('installed %s -> %s' % (PACKAGE_DIR, dst_pkg))

    dst_entry = os.path.join(mods_dir, MOD_ENTRY)
    shutil.copy2(entry_src, dst_entry)
    _log('installed %s' % MOD_ENTRY)

    # Optional map selector from the same Offline tree
    map_sel = os.path.join(OFFLINE_MOD_SRC, 'mod_Map_selector_v120.py')
    if os.path.isfile(map_sel):
        shutil.copy2(map_sel, os.path.join(mods_dir, 'mod_Map_selector_v120.py'))
        _log('installed mod_Map_selector_v120.py')

    targets = [dst_entry]
    map_dst = os.path.join(mods_dir, 'mod_Map_selector_v120.py')
    if os.path.isfile(map_dst):
        targets.append(map_dst)
    targets.extend(_iter_python_files(dst_pkg))

    deploy_pkg = HERE
    if deploy_pkg not in sys.path:
        sys.path.insert(0, deploy_pkg)
    from install_multiclient import compile_pyc, find_python27, verify_pyc_magic

    if python27 is None:
        python27 = find_python27()
    if not python27:
        _log('WARNING: Python 2.7 not found; skip .pyc')
        return 2

    _log('compiling %d files with %s' % (len(targets), python27))
    failures = []
    for py_path in targets:
        pyc_path = py_path + 'c'
        if not compile_pyc(py_path, pyc_path, python27=python27):
            failures.append(py_path)
            continue
        ok, magic, _head = verify_pyc_magic(pyc_path)
        if not ok:
            failures.append('%s (magic=%s)' % (py_path, magic))
    if failures:
        for item in failures:
            _log('compile FAILED: %s' % item)
        return 1
    _log('all .pyc written (magic=62211)')

    # Ensure auto-login flag exists next to win64 (cwd when launched from win64)
    flag_name = 'offline_autologin.flag'
    for folder in (game_root, os.path.join(game_root, 'win64')):
        flag_path = os.path.join(folder, flag_name)
        if not os.path.isfile(flag_path):
            try:
                with open(flag_path, 'wb') as handle:
                    handle.write(b'')
                _log('created %s' % flag_path)
            except Exception as exc:
                _log('flag create failed (%s): %s' % (flag_path, exc))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install Offline hangar mod')
    parser.add_argument('--game-root', default=DEFAULT_GAME_ROOT)
    parser.add_argument('--python27', default=None)
    args = parser.parse_args(argv)
    return install(args.game_root, python27=args.python27)


if __name__ == '__main__':
    sys.exit(main())
