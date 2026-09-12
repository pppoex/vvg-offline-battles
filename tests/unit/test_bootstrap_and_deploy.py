# -*- coding: utf-8 -*-
"""Unit tests for the in-game bootstrap and deploy layout helpers."""
from __future__ import print_function

import os
import shutil
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MULTICLIENT = os.path.join(ROOT, 'src', 'multiclient')
CLIENT = os.path.join(ROOT, 'src', 'client')
if MULTICLIENT not in sys.path:
    sys.path.insert(0, MULTICLIENT)

import instance_guard as ig  # noqa: E402


def _load_bootstrap():
    """Load src/client/vvg_instance_guard/bootstrap.py with package alias."""
    import imp

    # Make `from vvg_instance_guard import instance_guard` work.
    if 'vvg_instance_guard' not in sys.modules:
        pkg = types.ModuleType('vvg_instance_guard')
        pkg.instance_guard = ig
        sys.modules['vvg_instance_guard'] = pkg

    # Also register the real package dir so relative files resolve.
    pkg_dir = os.path.join(CLIENT, 'vvg_instance_guard')
    if pkg_dir not in getattr(sys, 'path', []):
        # Prefer loading bootstrap by absolute path; no need for path entry
        # when the package module is already in sys.modules.
        pass

    path = os.path.join(pkg_dir, 'bootstrap.py')
    return imp.load_source('vvg_bootstrap_under_test', path)


class NativeBridgePathWin64Tests(unittest.TestCase):
    """2.3.1.2 layout: <root>/win64/WorldOfTanks.exe + <root>/mods/2.3.1.2/."""

    def setUp(self):
        self._old = os.environ.pop('VVG_INSTANCE_GUARD_PATH', None)

    def tearDown(self):
        if self._old is None:
            os.environ.pop('VVG_INSTANCE_GUARD_PATH', None)
        else:
            os.environ['VVG_INSTANCE_GUARD_PATH'] = self._old

    def test_env_override_beats_all(self):
        os.environ['VVG_INSTANCE_GUARD_PATH'] = r'C:\x\guard.pyd'
        self.assertEqual(
            ig._native_bridge_path(executable=r'C:\game\win64\WorldOfTanks.exe'),
            r'C:\x\guard.pyd')

    def test_exe_sibling_pyd_found(self):
        root = tempfile.mkdtemp(prefix='vvg_path_')
        try:
            win64 = os.path.join(root, 'win64')
            os.makedirs(win64)
            exe = os.path.join(win64, 'WorldOfTanks.exe')
            open(exe, 'wb').close()
            pyd = os.path.join(win64, 'vvg_instance_guard_native.pyd')
            open(pyd, 'wb').close()
            self.assertEqual(ig._native_bridge_path(executable=exe), pyd)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_install_root_mods_pyd_found(self):
        root = tempfile.mkdtemp(prefix='vvg_path_')
        try:
            win64 = os.path.join(root, 'win64')
            mods = os.path.join(root, 'mods', ig.GAME_VERSION_DIR)
            os.makedirs(win64)
            os.makedirs(mods)
            exe = os.path.join(win64, 'WorldOfTanks.exe')
            open(exe, 'wb').close()
            pyd = os.path.join(mods, ig.NATIVE_FILENAME)
            open(pyd, 'wb').close()
            self.assertEqual(ig._native_bridge_path(executable=exe), pyd)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class BootstrapModuleTests(unittest.TestCase):
    def setUp(self):
        ig.reset_state_for_tests()

    def tearDown(self):
        ig.reset_state_for_tests()

    def test_bootstrap_imports_and_noop_without_env(self):
        bootstrap = _load_bootstrap()
        self.assertTrue(hasattr(bootstrap, 'init'))
        self.assertTrue(hasattr(bootstrap, 'fini'))

        bootstrap._started = False
        bootstrap._client_guard_released = False
        bootstrap._release_error = None
        old = os.environ.pop('VVG_ALLOW_MULTIPLE_CLIENTS', None)
        try:
            bootstrap.init()
            self.assertFalse(bootstrap.guard_released())
        finally:
            if old is not None:
                os.environ['VVG_ALLOW_MULTIPLE_CLIENTS'] = old
            bootstrap.fini()

    def test_bootstrap_releases_when_env_and_releaser_ok(self):
        bootstrap = _load_bootstrap()
        # Patch release path: inject a fake releaser into instance_guard
        # used by bootstrap via the aliased package module.
        calls = []

        def fake_releaser():
            calls.append(1)
            return True

        original = ig.release_if_requested
        ig.release_if_requested = (
            lambda environ=None, releaser=None: original(
                environ=environ, releaser=fake_releaser
                if releaser is None else releaser))
        bootstrap._started = False
        bootstrap._client_guard_released = False
        bootstrap._release_error = None
        old = os.environ.get('VVG_ALLOW_MULTIPLE_CLIENTS')
        os.environ['VVG_ALLOW_MULTIPLE_CLIENTS'] = '1'
        try:
            bootstrap.init()
            self.assertTrue(bootstrap.guard_released())
            self.assertEqual(calls, [1])
        finally:
            ig.release_if_requested = original
            if old is None:
                os.environ.pop('VVG_ALLOW_MULTIPLE_CLIENTS', None)
            else:
                os.environ['VVG_ALLOW_MULTIPLE_CLIENTS'] = old
            bootstrap.fini()


class ModEntryTests(unittest.TestCase):
    def test_entry_file_exists_and_declares_init(self):
        entry = os.path.join(CLIENT, 'mod_vvg_instance_guard.py')
        self.assertTrue(os.path.isfile(entry))
        with open(entry, 'r') as handle:
            text = handle.read()
        self.assertIn('def init()', text)
        self.assertIn('def fini()', text)
        self.assertIn('bootstrap', text)


class DeployScriptTests(unittest.TestCase):
    def test_deploy_module_loads(self):
        import imp
        path = os.path.join(ROOT, 'src', 'deploy', 'install_multiclient.py')
        self.assertTrue(os.path.isfile(path))
        deploy = imp.load_source('install_multiclient_under_test', path)
        self.assertEqual(deploy.MOD_ENTRY, 'mod_vvg_instance_guard.py')
        self.assertEqual(deploy.PACKAGE_DIR, 'vvg_instance_guard')
        self.assertIn('res_mods', deploy.RES_MODS_REL)
        self.assertIn('mods', deploy.MODS_REL)

    def test_deploy_dry_run_lists_files(self):
        import imp
        path = os.path.join(ROOT, 'src', 'deploy', 'install_multiclient.py')
        deploy = imp.load_source('install_multiclient_under_test2', path)
        game_root = os.path.join(ROOT, 'dist', '_dry_game_root')
        os.makedirs(os.path.join(game_root, 'win64'))
        try:
            planned = deploy.install(game_root, dry_run=True)
            names = [os.path.basename(dst) for _, dst, _ in planned]
            self.assertIn('mod_vvg_instance_guard.py', names)
            self.assertIn('instance_guard.py', names)
            self.assertIn('__init__.py', names)
            self.assertIn('bootstrap.py', names)
        finally:
            shutil.rmtree(game_root, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
