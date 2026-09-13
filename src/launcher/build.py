# -*- coding: utf-8 -*-
"""One-shot workspace build under build/ (mirrors src/).

Components:
  native — MSVC x64 multiclient artifacts (.pyd / .exe)
  pyc    — stage pure-Python sources and compile to Python 2.7 .pyc

Outputs (never written into src/):

  build/multiclient/native/vvg_instance_guard_native.pyd
  build/multiclient/native/vvg_worker_starter.exe
  build/client/**.pyc
  build/protocol/**.pyc
  build/sdk/**.pyc
  build/multiclient/**.pyc
  build/offline/**.pyc
"""
from __future__ import absolute_import, division, print_function

import os
import shutil
import subprocess

from launcher import bytecode as bytemod
from launcher import paths as pathmod
from launcher import ports

# Components that currently need a real build step.
COMPONENTS = ('native', 'pyc')

NATIVE_REL = os.path.join('build', 'multiclient', 'native')
NATIVE_OUTPUTS = (
    'vvg_instance_guard_native.pyd',
    'vvg_worker_starter.exe',
)
# Intermediate MSVC leftovers that stay under build/ but are not install sources.
NATIVE_INTERMEDIATES = (
    'instance_guard.obj',
    'worker_starter.obj',
    'build_native.bat',
    'vvg_instance_guard_native.exp',
    'vvg_instance_guard_native.lib',
)


def build_dir(workspace=None):
    """Workspace build/ root (artifacts only; src stays pure source)."""
    root = pathmod.workspace_root() if workspace is None else workspace
    return os.path.join(root, 'build')


def native_out_dir(workspace=None):
    return os.path.join(pathmod.workspace_root() if workspace is None
                        else workspace, *NATIVE_REL.split(os.sep))


def select_components(only=None, skip=None):
    if only and skip:
        raise SystemExit('pass only one of --only / --skip')
    names = list(COMPONENTS)
    if only:
        if only not in COMPONENTS:
            raise SystemExit(
                'unknown component %r (choose from %s)'
                % (only, ', '.join(COMPONENTS)))
        names = [only]
    if skip:
        if skip not in COMPONENTS:
            raise SystemExit(
                'unknown component %r (choose from %s)'
                % (skip, ', '.join(COMPONENTS)))
        names = [n for n in names if n != skip]
    return names


def find_build_script(workspace=None):
    root = pathmod.workspace_root() if workspace is None else workspace
    return os.path.join(
        root, 'src', 'multiclient', 'native', 'build.ps1')


def clean_native(workspace=None):
    """Remove build/multiclient/native (artifacts only)."""
    out = native_out_dir(workspace)
    if os.path.isdir(out):
        shutil.rmtree(out)
        ports.log('cleaned %s' % out)
    else:
        ports.log('nothing to clean at %s' % out)
    return 0


def build_native(workspace=None, log=None):
    """Run MSVC build.ps1; outputs land in build/multiclient/native/."""
    log = log or ports.log
    workspace = workspace or pathmod.workspace_root()
    script = find_build_script(workspace)
    if not os.path.isfile(script):
        raise SystemExit('missing native build script: %s' % script)

    out_dir = native_out_dir(workspace)
    pathmod.ensure_dir(out_dir)

    # Prefer the PowerShell host; fall back to powershell.exe.
    shell = shutil.which('powershell') or shutil.which('pwsh')
    if not shell:
        raise SystemExit(
            'PowerShell not found; cannot run %s' % script)

    cmd = [
        shell,
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', script,
    ]
    log('running native build: %s' % ' '.join(cmd))
    proc = subprocess.Popen(cmd, cwd=workspace)
    code = proc.wait()
    if code != 0:
        log('native build failed with exit %s' % code)
        return code

    missing = []
    for name in NATIVE_OUTPUTS:
        path = os.path.join(out_dir, name)
        if not os.path.isfile(path):
            missing.append(path)
        else:
            log('ok: %s (%d bytes)'
                % (path, os.path.getsize(path)))
    if missing:
        log('ERROR: missing outputs:')
        for path in missing:
            log('  %s' % path)
        return 1

    log('native artifacts under %s' % out_dir)
    return 0


def build_pyc_component(workspace=None, python27=None, log=None):
    """Stage sources into build/ and compile Python 2.7 .pyc."""
    return bytemod.build_pyc(
        workspace=workspace, python27=python27, log=log)


def build_all(only=None, skip=None, clean=False, python27=None,
              workspace=None, log=None):
    """Entry for `python -m launcher build`."""
    log = log or ports.log
    workspace = workspace or pathmod.workspace_root()
    selected = select_components(only=only, skip=skip)
    log('build components=%s clean=%s' % (','.join(selected), bool(clean)))

    if clean:
        if 'native' in selected:
            clean_native(workspace)
        if 'pyc' in selected:
            bytemod.clean_pyc(workspace)

    results = {}
    if 'native' in selected:
        try:
            results['native'] = build_native(workspace=workspace, log=log)
        except SystemExit as exc:
            log('native FAILED: %s' % exc)
            results['native'] = 1
    if 'pyc' in selected:
        try:
            results['pyc'] = build_pyc_component(
                workspace=workspace, python27=python27, log=log)
        except SystemExit as exc:
            log('pyc FAILED: %s' % exc)
            results['pyc'] = 1

    failed = [k for k, v in results.items() if v != 0]
    for name in selected:
        log('component %s -> %s' % (name, results.get(name)))
    if failed:
        log('FAILED: %s' % ', '.join(failed))
        return 1
    log('build complete (artifacts under build/, game loads .pyc only)')
    log('next: python -m launcher deploy')
    return 0
