# -*- coding: utf-8 -*-
"""Deploy the multi-client guard into a WoT 2.3.1.2 install.

Installs (never touches game exe/dll/pkg):

  res_mods/2.3.1.2/scripts/client/gui/mods/
      mod_vvg_instance_guard.py
      mod_vvg_instance_guard.pyc
      vvg_instance_guard/
          __init__.py
          __init__.pyc
          bootstrap.py
          bootstrap.pyc
          instance_guard.py          (copied from src/multiclient)
          instance_guard.pyc

  mods/2.3.1.2/
      vvg_instance_guard_native.pyd

  win64/                              (optional convenience copies)
      vvg_instance_guard_native.pyd
      vvg_worker_starter.exe

The 2.3.1.2 client loads only .pyc from res_mods (embedded Python 2.7),
so every pure-Python file is compiled with D:\\Python27\\python.exe and the
matching .pyc is installed alongside the .py source.

Usage (from workspace root, any Python 2.7+ or 3):

  python src/deploy/install_multiclient.py
  python src/deploy/install_multiclient.py --game-root "D:\\WOT\\World_of_Tanks_EU_Offline_2.3.1.2"
"""
from __future__ import print_function

import argparse
import os
import shutil
import struct
import subprocess
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

# Python 2.7 bytecode magic: 62211 = 0xF303, then \r\n -> bytes 03 f3 0d 0a.
# Same as Offline2.3.1.2 headers: "Python bytecode version base 2.7 (62211)".
PY27_MAGIC = 62211
PY27_MAGIC_BYTES = struct.pack('<H', PY27_MAGIC) + b'\r\n'  # b'\x03\xf3\r\n'

# Prefer the workspace symlink, then the well-known install.
PYTHON27_CANDIDATES = (
    os.path.join(ROOT, '.py27', 'python.exe'),
    r'D:\Python27\python.exe',
)

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


def find_python27(explicit=None):
    """Locate a Python 2.7 interpreter for bytecode compilation."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get('VVG_PYTHON27')
    if env:
        candidates.append(env)
    candidates.extend(PYTHON27_CANDIDATES)
    for cand in candidates:
        if cand and os.path.isfile(cand):
            return os.path.abspath(cand)
    return None


def verify_pyc_magic(pyc_path):
    """Return (ok, magic_int, magic_bytes) for a .pyc file."""
    with open(pyc_path, 'rb') as handle:
        head = handle.read(4)
    if len(head) < 4:
        return False, None, head
    magic_int = struct.unpack('<H', head[:2])[0]
    return head == PY27_MAGIC_BYTES, magic_int, head


def compile_pyc(py_path, pyc_path, python27=None):
    """Compile py_path to pyc_path using a Python 2.7 interpreter.

    Returns the interpreter path used. Raises SystemExit on failure so a
    mis-deployed mod never reaches the game without bytecode.
    """
    python27 = python27 or find_python27()
    if not python27:
        raise SystemExit(
            'Python 2.7 interpreter not found (need D:\\Python27\\python.exe '
            'or workspace .py27 symlink). WoT 2.3.1.2 loads only .pyc; '
            'refusing to deploy without compilation.')

    parent = os.path.dirname(pyc_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)

    # Small driver so the destination path is explicit and doraise is on.
    code = (
        'import py_compile, sys\n'
        'src, dst = sys.argv[1], sys.argv[2]\n'
        'py_compile.compile(src, dst, doraise=True)\n'
    )
    cmd = [python27, '-c', code, os.path.abspath(py_path),
           os.path.abspath(pyc_path)]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    if proc.returncode != 0:
        detail = err or out or b'unknown error'
        if not isinstance(detail, str):
            detail = detail.decode('utf-8', 'replace')
        raise SystemExit(
            'py_compile failed for %s (exit %s): %s'
            % (py_path, proc.returncode, detail.strip()))

    ok, magic_int, magic_bytes = verify_pyc_magic(pyc_path)
    if not ok:
        raise SystemExit(
            'bad .pyc magic for %s: got %r (expected Python 2.7 %s / %r)'
            % (pyc_path, magic_bytes, PY27_MAGIC, PY27_MAGIC_BYTES))
    _log('compiled %s -> %s (magic %s)' % (py_path, pyc_path, magic_int))
    return python27


def install(game_root, dry_run=False, python27=None):
    game_root = os.path.abspath(game_root)
    if not os.path.isdir(game_root):
        raise SystemExit('game root not found: %s' % game_root)
    if not os.path.isfile(os.path.join(game_root, 'win64', 'WorldOfTanks.exe')):
        _log('warning: win64/WorldOfTanks.exe not found under %s '
             '(continuing anyway)' % game_root)

    python27 = find_python27(python27)
    if dry_run and not python27:
        _log('warning: Python 2.7 not found; real install would fail')
    elif not dry_run:
        _log('python27: %s' % python27)

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

    # Pure-Python files: install .py (kept for tooling) + .pyc (game loads).
    pure_py = [
        (entry_src, os.path.join(mods_dest, MOD_ENTRY), 'mod entry'),
        (init_src, os.path.join(pkg_dest, '__init__.py'), 'package init'),
        (bootstrap_src, os.path.join(pkg_dest, 'bootstrap.py'), 'bootstrap'),
        (guard_src, os.path.join(pkg_dest, 'instance_guard.py'),
         'instance_guard'),
    ]

    planned = []
    for src, dst, label in pure_py:
        planned.append((src, dst, label))
        planned.append((src, dst[:-3] + '.pyc', label + ' (pyc)'))
    if native_src:
        planned.append((native_src, native_mods_dest, 'native pyd (mods)'))
        planned.append((native_src, native_win64_dest, 'native pyd (win64)'))
    if starter_src:
        planned.append((starter_src, starter_dest, 'worker starter'))

    if dry_run:
        for src, dst, label in planned:
            _log('would install %s -> %s' % (label, dst))
        return planned

    for src, dst, label in pure_py:
        _copy_file(src, dst, label)
        pyc_dst = dst[:-3] + '.pyc'
        compile_pyc(src, pyc_dst, python27=python27)
        _log('installed %s (pyc) -> %s' % (label, pyc_dst))

    for src, dst, label in planned:
        if label.endswith('(pyc)'):
            continue
        if (src, dst, label) in pure_py:
            continue
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
        '--python27', default=None,
        help='path to Python 2.7 interpreter used for py_compile '
             '(default: .py27 symlink or D:\\Python27\\python.exe)')
    parser.add_argument(
        '--dry-run', action='store_true',
        help='print planned copies without writing')
    args = parser.parse_args(argv)
    install(args.game_root, dry_run=args.dry_run, python27=args.python27)
    return 0


if __name__ == '__main__':
    sys.exit(main())
