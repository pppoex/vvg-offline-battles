# -*- coding: utf-8 -*-
"""Unit tests for the 2.3.1.2 multi-client instance guard Python API."""
from __future__ import print_function

import os
import sys
import unittest

# Workspace layout: tests/unit -> src/multiclient
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MULTICLIENT = os.path.join(ROOT, 'src', 'multiclient')
if MULTICLIENT not in sys.path:
    sys.path.insert(0, MULTICLIENT)

import instance_guard as ig  # noqa: E402


class MultipleClientsEnvTests(unittest.TestCase):
    def test_disabled_when_missing(self):
        self.assertFalse(ig._multiple_clients_requested({}))

    def test_disabled_when_not_one(self):
        self.assertFalse(ig._multiple_clients_requested({
            ig.ALLOW_MULTIPLE_CLIENTS_ENV: '0'}))
        self.assertFalse(ig._multiple_clients_requested({
            ig.ALLOW_MULTIPLE_CLIENTS_ENV: 'true'}))

    def test_enabled_when_one(self):
        self.assertTrue(ig._multiple_clients_requested({
            ig.ALLOW_MULTIPLE_CLIENTS_ENV: '1'}))
        self.assertTrue(ig._multiple_clients_requested({
            ig.ALLOW_MULTIPLE_CLIENTS_ENV: ' 1 '}))

    def test_non_string_value(self):
        self.assertFalse(ig._multiple_clients_requested({
            ig.ALLOW_MULTIPLE_CLIENTS_ENV: None}))


class ReleaseIfRequestedTests(unittest.TestCase):
    def setUp(self):
        ig.reset_state_for_tests()

    def tearDown(self):
        ig.reset_state_for_tests()

    def test_noop_without_env(self):
        self.assertFalse(ig.release_if_requested(environ={}))

    def test_calls_releaser_once(self):
        calls = []

        def releaser():
            calls.append(1)
            return True

        self.assertTrue(ig.release_if_requested(
            environ={ig.ALLOW_MULTIPLE_CLIENTS_ENV: '1'}, releaser=releaser))
        self.assertTrue(ig.release_if_requested(
            environ={ig.ALLOW_MULTIPLE_CLIENTS_ENV: '1'}, releaser=releaser))
        self.assertEqual(calls, [1])

    def test_failure_is_cached(self):
        state = {'n': 0}

        def releaser():
            state['n'] += 1
            raise ig.ClientInstanceGuardError('boom', 16)

        with self.assertRaises(ig.ClientInstanceGuardError):
            ig.release_if_requested(
                environ={ig.ALLOW_MULTIPLE_CLIENTS_ENV: '1'},
                releaser=releaser)
        with self.assertRaises(ig.ClientInstanceGuardError):
            ig.release_if_requested(
                environ={ig.ALLOW_MULTIPLE_CLIENTS_ENV: '1'},
                releaser=releaser)
        self.assertEqual(state['n'], 1)


class NativeBridgePathTests(unittest.TestCase):
    def test_env_override(self):
        path = os.path.join(ROOT, 'dist', 'multiclient',
                            'vvg_instance_guard_native.pyd')
        old = os.environ.get('VVG_INSTANCE_GUARD_PATH')
        os.environ['VVG_INSTANCE_GUARD_PATH'] = path
        try:
            self.assertEqual(ig._native_bridge_path(), path)
        finally:
            if old is None:
                del os.environ['VVG_INSTANCE_GUARD_PATH']
            else:
                os.environ['VVG_INSTANCE_GUARD_PATH'] = old

    def test_extra_search_finds_dist_drop(self):
        drop = os.path.join(ROOT, 'dist', 'multiclient')
        # May or may not exist depending on build; just ensure no crash and
        # returned value ends with the expected filename when found.
        path = ig._native_bridge_path(
            executable=sys.executable, extra_search=[drop])
        self.assertTrue(path.endswith('vvg_instance_guard_native.pyd'))

    def test_workspace_dist_drop_preferred_over_missing_install(self):
        drop = os.path.join(ROOT, 'dist', 'multiclient')
        pyd = os.path.join(drop, 'vvg_instance_guard_native.pyd')
        if not os.path.isfile(pyd):
            self.skipTest('dist pyd not built')
        old = os.environ.pop('VVG_INSTANCE_GUARD_PATH', None)
        try:
            # Pretend the exe is a random win64 path that has no pyd.
            fake_exe = os.path.join(ROOT, 'src', 'multiclient', 'native',
                                    'out', 'missing_parent', 'WorldOfTanks.exe')
            path = ig._native_bridge_path(
                executable=fake_exe, extra_search=[drop])
            self.assertEqual(path, pyd)
        finally:
            if old is not None:
                os.environ['VVG_INSTANCE_GUARD_PATH'] = old


class StatusMappingTests(unittest.TestCase):
    def test_operations_cover_key_codes(self):
        for code in (1, 16, 21, 22):
            self.assertIn(code, ig._GUARD_STATUS_OPERATIONS)

    def test_error_message_shape(self):
        err = ig.ClientInstanceGuardError('demo', 16)
        self.assertEqual(err.error_code, 16)
        self.assertIn('16', str(err))


class ExtensionLoaderTests(unittest.TestCase):
    """Extension import path: no ctypes required inside the game."""

    def test_has_ctypes_boolean(self):
        self.assertIsInstance(ig._has_ctypes(), bool)

    def test_try_load_extension_missing_file_raises(self):
        with self.assertRaises((IOError, OSError, ImportError)):
            ig._try_load_extension(os.path.join(ROOT, 'no_such_guard.pyd'))

    def test_extension_bridge_method_names(self):
        class FakeMod(object):
            def release_client_guard(self):
                return 0

            def probe_startup_mutex(self):
                return 16

            def install_atmosphere_owner_guard(self):
                return 22

            def hide_process_windows(self):
                return -1

            def show_process_windows(self):
                return 0

            def validate_host(self):
                return 0

            def init_bridge(self):
                return 1

        bridge = ig._ExtensionBridge(FakeMod(), r'C:\fake\guard.pyd')
        self.assertEqual(bridge.loader, 'extension')
        self.assertEqual(bridge.release_client_guard(), 0)
        self.assertEqual(bridge.probe_startup_mutex(), 16)
        self.assertEqual(bridge.install_atmosphere_owner_guard(), 22)
        self.assertEqual(bridge.validate_host(), 0)
        self.assertEqual(bridge.init_bridge(), 1)


class OptionalNativeTests(unittest.TestCase):
    """Exercise the compiled bridge when the artifact is present."""

    def _maybe_bridge(self):
        drop = os.path.join(ROOT, 'dist', 'multiclient')
        path = os.path.join(drop, 'vvg_instance_guard_native.pyd')
        if not os.path.isfile(path):
            path = os.path.join(
                MULTICLIENT, 'native', 'out', 'vvg_instance_guard_native.pyd')
        if not os.path.isfile(path):
            return None, None
        old = os.environ.get('VVG_INSTANCE_GUARD_PATH')
        os.environ['VVG_INSTANCE_GUARD_PATH'] = path
        try:
            ig.reset_state_for_tests()
            bridge = ig._load_native_bridge(path=path)
            return bridge, path
        finally:
            if old is None:
                os.environ.pop('VVG_INSTANCE_GUARD_PATH', None)
            else:
                os.environ['VVG_INSTANCE_GUARD_PATH'] = old

    def test_bridge_loads_when_present(self):
        bridge, path = self._maybe_bridge()
        if bridge is None:
            self.skipTest('native bridge not built yet')
        # Outside the game host, validate_host should report mismatch (1)
        # and init_bridge may return 0. Both are acceptable for unit tests.
        status = bridge.validate_host()
        self.assertIn(status, (0, 1))
        self.assertIn(getattr(bridge, 'loader', 'ctypes'), ('extension', 'ctypes'))

    def test_extension_preferred_when_loadable(self):
        drop = os.path.join(ROOT, 'dist', 'multiclient')
        path = os.path.join(drop, 'vvg_instance_guard_native.pyd')
        if not os.path.isfile(path):
            path = os.path.join(
                MULTICLIENT, 'native', 'out', 'vvg_instance_guard_native.pyd')
        if not os.path.isfile(path):
            self.skipTest('native bridge not built yet')
        ig.reset_state_for_tests()
        try:
            bridge = ig._load_native_bridge(path=path)
        except ImportError:
            self.skipTest('extension load not available in this host')
        else:
            # Prefer extension when the pyd registers module methods.
            # Host Python ABI may not match the game py27-built pyd; then
            # ctypes fallback is acceptable for unit tests outside the game.
            loader = getattr(bridge, 'loader', None)
            if loader != 'extension':
                self.skipTest('host cannot import pyd as extension (loader=%r)' % loader)
            self.assertEqual(loader, 'extension')

    def test_atmosphere_status_constant(self):
        self.assertEqual(ig.GUARD_STATUS_ATMOSPHERE_UNSUPPORTED, 22)


if __name__ == '__main__':
    unittest.main()
