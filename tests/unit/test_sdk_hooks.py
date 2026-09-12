# -*- coding: utf-8 -*-
"""SDK hooks 单元测试。"""
from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SDK_ROOT = os.path.join(ROOT, 'src')
if SDK_ROOT not in sys.path:
    sys.path.insert(0, SDK_ROOT)

from sdk import hooks  # noqa: E402


class _Target(object):
    def greet(self, name):
        return 'hello ' + name

    def _private_helper(self):
        return 'secret'

    def call_private(self):
        return self._private_helper()


class ResolveNameTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(hooks.resolve_name(_Target, 'greet'), 'greet')

    def test_mangled_private(self):
        self.assertEqual(hooks.resolve_name(_Target, '_private_helper'),
                         '_private_helper')

    def test_double_underscore_mangling(self):
        # class _Target 上 __foo -> _Target_foo
        class Box(object):
            def __init__(self):
                self.value = 1

            def __hidden(self):
                return self.value

            def run(self):
                return self.__hidden()

        self.assertEqual(hooks.resolve_name(Box, '__hidden'), '_Box__hidden')
        self.assertTrue(hooks.resolve_name(Box, '__hidden') != '__hidden'
                        or hasattr(Box, '__hidden'))


class OverrideTests(unittest.TestCase):
    def test_override_wraps_original(self):
        class Holder(object):
            def value(self):
                return 1

        @hooks.override(Holder, 'value')
        def double_value(original, *args, **kwargs):
            return original(*args, **kwargs) * 2

        self.assertEqual(Holder().value(), 2)

    def test_override_idempotent(self):
        class Holder(object):
            def value(self):
                return 1

        calls = []

        @hooks.override(Holder, 'value')
        def patch_a(original, *args, **kwargs):
            calls.append('a')
            return original(*args, **kwargs)

        first = Holder.value

        @hooks.override(Holder, 'value')
        def patch_b(original, *args, **kwargs):
            calls.append('b')
            return original(*args, **kwargs)

        second = Holder.value
        # 第二次 patch 同 tag 不叠加；不同 tag 会再包一层
        # patch_a 与 patch_b tag 不同，因此会再包
        self.assertNotEqual(first, second)

        class Holder2(object):
            def value(self):
                return 1

        @hooks.override(Holder2, 'value')
        def p1(original, *args, **kwargs):
            return original(*args, **kwargs) + 1

        again = hooks.override(Holder2, 'value')(p1)
        self.assertIs(again, Holder2.value)

    def test_missing_attribute_returns_replacement(self):
        class Empty(object):
            pass

        @hooks.override(Empty, 'nope')
        def fallback(original, *args, **kwargs):
            return 'fallback'

        # override 失败时返回 replacement 本身（非 wrapper）
        self.assertEqual(fallback(None), 'fallback')

    def test_chain_injects_original(self):
        class Holder(object):
            def run(self, x):
                return x

        @hooks.override(Holder, 'run')
        def add_one(original, self, x):
            return original(self, x) + 1

        @hooks.override(Holder, 'run')
        def mul_ten(original, self, x):
            return original(self, x) * 10

        # 最后挂上的先执行：mul_ten(add_one(run))
        self.assertEqual(Holder().run(1), 20)


class SetAttrTests(unittest.TestCase):
    def test_set_attr(self):
        class Holder(object):
            pass

        self.assertTrue(hooks.set_attr(Holder, 'flag', 42))
        self.assertEqual(Holder.flag, 42)

    def test_setAttr_alias(self):
        self.assertIs(hooks.setAttr, hooks.set_attr)


if __name__ == '__main__':
    unittest.main()
