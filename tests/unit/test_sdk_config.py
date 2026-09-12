# -*- coding: utf-8 -*-
"""SDK config 单元测试。"""
from __future__ import absolute_import, division, print_function

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SDK_ROOT = os.path.join(ROOT, 'src')
if SDK_ROOT not in sys.path:
    sys.path.insert(0, SDK_ROOT)

from sdk import config  # noqa: E402


class ConfigDefaultsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix='vvg_cfg_test_')
        self._cwd = os.getcwd()
        os.chdir(self._tmp)
        config.reset_for_tests()

    def tearDown(self):
        config.reset_for_tests()
        os.chdir(self._cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_server_address_default(self):
        host, port = config.get_server_address()
        self.assertEqual(host, '127.0.0.1')
        self.assertEqual(port, 28782)

    def test_client_mode_default(self):
        self.assertEqual(config.get_client_mode(), 'player')

    def test_client_mode_invalid_falls_back(self):
        with open('vvg_config.json', 'w') as f:
            json.dump({'CLIENT_MODE': 'bogus'}, f)
        config.load_overrides(force=True)
        self.assertEqual(config.get_client_mode(), 'player')

    def test_reconnect_policy(self):
        policy = config.get_reconnect_policy()
        self.assertTrue(policy['enabled'])
        self.assertEqual(policy['max_attempts'], 10)
        self.assertAlmostEqual(policy['initial_delay'], 0.5)

    def test_tick_rates(self):
        rates = config.get_tick_rates()
        self.assertEqual(rates['server_hz'], 30)
        self.assertEqual(rates['snapshot_hz'], 15)

    def test_no_legacy_offline_constants(self):
        self.assertFalse(hasattr(config, 'OFFLINE_URL'))
        self.assertFalse(hasattr(config, 'OFFLINE_NAME'))


class ConfigOverrideTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix='vvg_cfg_ov_')
        self._cwd = os.getcwd()
        os.chdir(self._tmp)
        config.reset_for_tests()

    def tearDown(self):
        config.reset_for_tests()
        os.chdir(self._cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_json_override_port(self):
        with open('vvg_config.json', 'w') as f:
            json.dump({
                'SERVER_HOST': '192.168.1.50',
                'SERVER_PORT': '9999',
                '_comment': 'ignored',
            }, f)
        path = config.load_overrides()
        self.assertIsNotNone(path)
        host, port = config.get_server_address()
        self.assertEqual(host, '192.168.1.50')
        self.assertEqual(port, 9999)

    def test_comment_keys_skipped(self):
        with open('vvg_config.json', 'w') as f:
            json.dump({'_comment_SECRET': 'x', 'SERVER_PORT': 1234}, f)
        config.load_overrides()
        self.assertNotIn('_comment_SECRET', config._json_overrides)
        _, port = config.get_server_address()
        self.assertEqual(port, 1234)

    def test_get_type_coercion(self):
        config._json_overrides['x_bool'] = 1
        config._json_overrides['x_int'] = '42'
        config._json_overrides['x_float'] = '1.5'
        config._loaded = True
        self.assertIs(config._get('x_bool', False), True)
        self.assertEqual(config._get('x_int', 0), 42)
        self.assertAlmostEqual(config._get('x_float', 0.0), 1.5)

    def test_broken_json_does_not_crash(self):
        with open('vvg_config.json', 'w') as f:
            f.write('{not json')
        config.load_overrides()  # 不应抛异常
        _, port = config.get_server_address()
        self.assertEqual(port, 28782)


if __name__ == '__main__':
    unittest.main()
