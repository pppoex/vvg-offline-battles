# -*- coding: utf-8 -*-
"""Compile client-side Python to Python 2.7 .pyc under build/ (mirrors src/).

WoT 2.3.1.2 loads only .pyc (magic=62211). `python -m launcher build` must
therefore produce bytecode next to the source layout under build/:

  build/client/mod_vvg_client.py[.pyc]
  build/client/vvg_client/**
  build/client/offline_entry/mod_offhangar2.py[.pyc]
  build/protocol/**
  build/sdk/**
  build/multiclient/*.py[.pyc]          # pure Python only
  build/offline/mod_offhangar2.py[.pyc]
  build/offline/offhangar2/**           # Offline hangar package

Deploy still copies into the game res_mods tree (and may recompile there);
build/ is the workspace artifact store.
"""
from __future__ import absolute_import, division, print_function

import os
import shutil
import sys

from launcher import ports

# Reuse the proven 2.7 compiler from install_multiclient.
_DEPLOY_DIR = None


def _ensure_deploy_path():
    global _DEPLOY_DIR
    from launcher import paths as pathmod
    deploy_dir = os.path.join(pathmod.workspace_root(), 'src', 'deploy')
    if deploy_dir not in sys.path:
        sys.path.insert(0, deploy_dir)
    _DEPLOY_DIR = deploy_dir
    import install_multiclient  # noqa: F401
    return install_multiclient


def _iter_py_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip bytecode caches and nested build outputs.
        dirnames[:] = [
            d for d in dirnames
            if d not in ('__pycache__', 'out', 'build')
        ]
        for name in filenames:
            if name.endswith('.py'):
                yield os.path.join(dirpath, name)


def _copy_tree(src, dst, log, label):
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    log('staged %s -> %s' % (label, dst))


def _copy_file(src, dst, log, label):
    parent = os.path.dirname(dst)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    shutil.copy2(src, dst)
    log('staged %s -> %s' % (label, dst))


def default_sources(workspace=None):
    """List of (src_dir_or_file, build_dest, is_dir, label)."""
    from launcher import paths as pathmod
    root = pathmod.workspace_root() if workspace is None else workspace
    offline_mods = os.path.normpath(
        r'D:\Projects\Offline2.3.1.2\script\client\gui\mods')

    entries = [
        (
            os.path.join(root, 'src', 'client', 'vvg_client'),
            os.path.join(root, 'build', 'client', 'vvg_client'),
            True,
            'vvg_client',
        ),
        (
            os.path.join(root, 'src', 'client', 'offline_entry',
                         'mod_offhangar2.py'),
            os.path.join(root, 'build', 'client', 'offline_entry',
                         'mod_offhangar2.py'),
            False,
            'mod_offhangar2 entry',
        ),
        (
            os.path.join(root, 'src', 'client', 'mod_vvg_client.py'),
            os.path.join(root, 'build', 'client', 'mod_vvg_client.py'),
            False,
            'mod_vvg_client entry',
        ),
        (
            os.path.join(root, 'src', 'protocol'),
            os.path.join(root, 'build', 'protocol'),
            True,
            'protocol',
        ),
        (
            os.path.join(root, 'src', 'sdk'),
            os.path.join(root, 'build', 'sdk'),
            True,
            'sdk',
        ),
        (
            os.path.join(root, 'src', 'multiclient', 'instance_guard.py'),
            os.path.join(root, 'build', 'multiclient', 'instance_guard.py'),
            False,
            'instance_guard',
        ),
        (
            os.path.join(root, 'src', 'client', 'vvg_instance_guard',
                         '__init__.py'),
            os.path.join(root, 'build', 'multiclient', '__init__.py'),
            False,
            'vvg_instance_guard __init__',
        ),
        (
            os.path.join(root, 'src', 'client', 'vvg_instance_guard',
                         'bootstrap.py'),
            os.path.join(root, 'build', 'multiclient', 'bootstrap.py'),
            False,
            'vvg_instance_guard bootstrap',
        ),
        (
            os.path.join(offline_mods, 'mod_offhangar2.py'),
            os.path.join(root, 'build', 'offline', 'mod_offhangar2.py'),
            False,
            'offline mod entry (unfixed fallback)',
        ),
        (
            os.path.join(offline_mods, 'offhangar2'),
            os.path.join(root, 'build', 'offline', 'offhangar2'),
            True,
            'offhangar2 package',
        ),
    ]
    # Prefer workspace-fixed Offline entry over raw Decompyle source.
    fixed = os.path.join(
        root, 'src', 'client', 'offline_entry', 'mod_offhangar2.py')
    if os.path.isfile(fixed):
        for index, item in enumerate(entries):
            if item[3] == 'offline mod entry (unfixed fallback)':
                entries[index] = (
                    fixed,
                    os.path.join(root, 'build', 'offline', 'mod_offhangar2.py'),
                    False,
                    'mod_offhangar2 (fixed entry)',
                )
                break
    return entries


def stage_sources(workspace=None, log=None):
    """Copy pure-Python sources into build/ (mirror layout)."""
    log = log or ports.log
    staged = []
    for src, dest, is_dir, label in default_sources(workspace):
        if is_dir:
            if not os.path.isdir(src):
                log('WARNING: missing %s (%s), skip' % (label, src))
                continue
            _copy_tree(src, dest, log, label)
            for path in _iter_py_files(dest):
                staged.append(path)
        else:
            if not os.path.isfile(src):
                log('WARNING: missing %s (%s), skip' % (label, src))
                continue
            _copy_file(src, dest, log, label)
            staged.append(dest)
    return staged


def compile_tree(files, python27, log=None):
    """Compile each .py to sibling .pyc with Python 2.7 (magic=62211)."""
    log = log or ports.log
    install_multiclient = _ensure_deploy_path()
    if not python27:
        raise SystemExit(
            'Python 2.7 interpreter not found; cannot produce .pyc '
            '(game loads only magic=62211). Set VVG_PYTHON27 or pass --python27')

    failures = []
    ok_count = 0
    for py_path in files:
        pyc_path = py_path + 'c'
        try:
            install_multiclient.compile_pyc(
                py_path, pyc_path, python27=python27)
            magic_ok, magic_int, _head = install_multiclient.verify_pyc_magic(
                pyc_path)
            if not magic_ok:
                failures.append('%s (magic=%s)' % (py_path, magic_int))
                continue
            ok_count += 1
        except SystemExit as exc:
            failures.append('%s (%s)' % (py_path, exc))
    if failures:
        for item in failures:
            log('compile FAILED: %s' % item)
        return ok_count, failures
    return ok_count, []


def clean_pyc(workspace=None):
    """Remove build bytecode roots (keep native/)."""
    from launcher import paths as pathmod
    root = pathmod.workspace_root() if workspace is None else workspace
    targets = (
        os.path.join(root, 'build', 'client'),
        os.path.join(root, 'build', 'protocol'),
        os.path.join(root, 'build', 'sdk'),
        os.path.join(root, 'build', 'offline'),
    )
    # multiclient pure-py sits beside native/ — remove .py/.pyc only.
    multi = os.path.join(root, 'build', 'multiclient')
    for path in targets:
        if os.path.isdir(path):
            shutil.rmtree(path)
            ports.log('cleaned %s' % path)
    if os.path.isdir(multi):
        for name in os.listdir(multi):
            if name.endswith(('.py', '.pyc')):
                os.remove(os.path.join(multi, name))
                ports.log('removed %s' % os.path.join(multi, name))
    return 0


def build_pyc(workspace=None, python27=None, log=None):
    """Stage sources under build/ then compile every .py → .pyc."""
    log = log or ports.log
    if python27 is None:
        install_multiclient = _ensure_deploy_path()
        python27 = install_multiclient.find_python27()
    if not python27:
        log('ERROR: Python 2.7 not found (need .py27 or D:\\Python27)')
        return 2

    log('python27: %s' % python27)
    staged = stage_sources(workspace=workspace, log=log)
    if not staged:
        log('ERROR: nothing staged under build/')
        return 1
    log('staged %d .py file(s); compiling bytecode…' % len(staged))
    ok_count, failures = compile_tree(staged, python27, log=log)
    if failures:
        log('bytecode FAILED (%d ok, %d failed)' % (ok_count, len(failures)))
        return 1
    log('bytecode ok: %d .pyc (magic=62211)' % ok_count)
    return 0
