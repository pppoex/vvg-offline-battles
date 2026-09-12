# -*- coding: utf-8 -*-
"""SDK log 单元测试。"""
from __future__ import absolute_import, division, print_function

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

from sdk import log  # noqa: E402


class LogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix='vvg_log_test_')
        self._cwd = os.getcwd()
        os.chdir(self._tmp)
        log.reset_for_tests()

    def tearDown(self):
        log.reset_for_tests()
        os.chdir(self._cwd)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_info_writes_file(self):
        log.info('hello %s', 'world')
        handle = log.open_file()
        self.assertIsNotNone(handle)
        path = os.path.join(self._tmp, log.LOG_NAME)
        self.assertTrue(os.path.isfile(path))
        with open(path, 'rb') as f:
            data = f.read().decode('utf-8', 'replace')
        self.assertIn('hello world', data)
        self.assertIn(log.PREFIX, data)

    def test_err_prefix(self):
        log.err('bad %d', 7)
        with open(os.path.join(self._tmp, log.LOG_NAME), 'rb') as f:
            data = f.read().decode('utf-8', 'replace')
        self.assertIn('ERROR: bad 7', data)

    def test_exc_records_context(self):
        try:
            raise ValueError('boom')
        except Exception:
            log.exc('my_context')
        with open(os.path.join(self._tmp, log.LOG_NAME), 'rb') as f:
            data = f.read().decode('utf-8', 'replace')
        self.assertIn('my_context', data)
        self.assertIn('ValueError', data)

    def test_guard_swallows(self):
        @log.guard('guarded')
        def explode():
            raise RuntimeError('nope')

        self.assertIsNone(explode())
        with open(os.path.join(self._tmp, log.LOG_NAME), 'rb') as f:
            data = f.read().decode('utf-8', 'replace')
        self.assertIn('guarded', data)

    def test_guard_passthrough(self):
        @log.guard('ok')
        def add(a, b):
            return a + b

        self.assertEqual(add(2, 3), 5)

    def test_info_without_args(self):
        log.info('plain')
        with open(os.path.join(self._tmp, log.LOG_NAME), 'rb') as f:
            data = f.read().decode('utf-8', 'replace')
        self.assertIn('plain', data)


if __name__ == '__main__':
    unittest.main()
