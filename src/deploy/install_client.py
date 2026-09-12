# -*- coding: utf-8 -*-
"""Deploy the VVG thin client into a WoT 2.3.1.2 install.

Installs (never touches game exe/dll/pkg):

  res_mods/2.3.1.2/scripts/client/gui/mods/
      mod_vvg_client.py (+ .pyc)
      vvg_client/          (+ .pyc for each .py)
      protocol/            (+ .pyc)   # vendored from src/protocol
      vvg_client/sdk/ ...  optional — sdk is imported when present

Usage (workspace root, any Python 2.7+ or 3):

  python src/deploy/install_client.py
  python src/deploy/install_client.py --game-root "D:\\WOT\\..."
"""
from __future__ import print_function

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CLIENT_SRC = os.path.join(ROOT, 'src', 'client')
PROTOCOL_SRC = os.path.join(ROOT, 'src', 'protocol')
SDK_SRC = os.path.join(ROOT, 'src', 'sdk')
DIST = os.path.join(ROOT, 'dist', 'thin_client')

DEFAULT_GAME_ROOT = os.path.normpath(
    r'D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2')

GAME_VERSION = '2.3.1.2'
MOD_ENTRY = 'mod_vvg_client.py'
PACKAGE_DIR = 'vvg_client'
RES_MODS_REL = os.path.join(
    'res_mods', GAME_VERSION, 'scripts', 'client', 'gui', 'mods')


def _log(message):
    sys.stdout.write('[install_client] %s\n' % message)
    sys.stdout.flush()


def _require_dir(path, what):
    if not os.path.isdir(path):
        raise SystemExit('missing %s: %s' % (what, path))
    return path


def _iter_python_files(root):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith('.py'):
                yield os.path.join(dirpath, name)


def _copy_tree(src, dst, label):
    if not os.path.isdir(src):
        raise SystemExit('missing %s: %s' % (label, src))
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    _log('installed %s -> %s' % (label, dst))


def _compile_all(python27, files):
    # Reuse the proven Py2.7 compiler from install_multiclient.
    deploy_pkg = os.path.dirname(os.path.abspath(__file__))
    if deploy_pkg not in sys.path:
        sys.path.insert(0, deploy_pkg)
    from install_multiclient import compile_pyc, verify_pyc_magic  # noqa: E402

    failures = []
    for py_path in files:
        pyc_path = py_path + 'c'
        ok = compile_pyc(py_path, pyc_path, python27=python27)
        if not ok:
            failures.append(py_path)
            continue
        magic_ok, magic_int, _head = verify_pyc_magic(pyc_path)
        if not magic_ok:
            failures.append('%s (magic=%s)' % (py_path, magic_int))
    return failures


def install(game_root, python27=None, skip_sdk=False, dry_run=False):
    game_root = os.path.normpath(game_root)
    mods_dir = os.path.join(game_root, RES_MODS_REL)
    _require_dir(CLIENT_SRC, 'client sources')
    _require_dir(PROTOCOL_SRC, 'protocol package')

    entry_src = os.path.join(CLIENT_SRC, MOD_ENTRY)
    if not os.path.isfile(entry_src):
        raise SystemExit('missing mod entry: %s' % entry_src)

    if not dry_run:
        if not os.path.isdir(mods_dir):
            os.makedirs(mods_dir)
        # Fresh package copies (remove stale trees first).
        _copy_tree(
            os.path.join(CLIENT_SRC, PACKAGE_DIR),
            os.path.join(mods_dir, PACKAGE_DIR),
            'vvg_client')
        _copy_tree(
            PROTOCOL_SRC,
            os.path.join(mods_dir, 'protocol'),
            'protocol')
        if not skip_sdk:
            sdk_dst = os.path.join(mods_dir, 'sdk')
            # Do not clobber a nested sdk inside vvg_client.
            if os.path.isdir(SDK_SRC):
                _copy_tree(SDK_SRC, sdk_dst, 'sdk')
        shutil.copy2(entry_src, os.path.join(mods_dir, MOD_ENTRY))
        _log('installed %s' % MOD_ENTRY)
    else:
        _log('dry-run: would install into %s' % mods_dir)

    if dry_run:
        return 0

    # Collect every pure-Python file that must be .pyc for the game.
    targets = [os.path.join(mods_dir, MOD_ENTRY)]
    for base in (PACKAGE_DIR, 'protocol', 'sdk'):
        base_dir = os.path.join(mods_dir, base)
        if os.path.isdir(base_dir):
            targets.extend(_iter_python_files(base_dir))
    targets = [p for p in targets if os.path.isfile(p)]

    if python27 is None:
        deploy_pkg = os.path.dirname(os.path.abspath(__file__))
        if deploy_pkg not in sys.path:
            sys.path.insert(0, deploy_pkg)
        from install_multiclient import find_python27
        python27 = find_python27()

    if not python27:
        _log('WARNING: Python 2.7 not found; skip .pyc compile')
        _log('set VVG_PYTHON27 or pass --python27')
        return 2

    _log('compiling %d files with %s' % (len(targets), python27))
    failures = _compile_all(python27, targets)
    if failures:
        for item in failures:
            _log('compile FAILED: %s' % item)
        return 1
    _log('all .pyc written (magic=62211)')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Install VVG thin client')
    parser.add_argument('--game-root', default=DEFAULT_GAME_ROOT)
    parser.add_argument('--python27', default=None)
    parser.add_argument('--skip-sdk', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    return install(
        args.game_root,
        python27=args.python27,
        skip_sdk=args.skip_sdk,
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    sys.exit(main())
