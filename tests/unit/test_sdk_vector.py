# -*- coding: utf-8 -*-
"""SDK math.vector 单元测试。"""
from __future__ import absolute_import, division, print_function

import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SDK_ROOT = os.path.join(ROOT, 'src')
if SDK_ROOT not in sys.path:
    sys.path.insert(0, SDK_ROOT)

from sdk.math.vector import Vector3, ZERO, UNIT_Z  # noqa: E402


class Vector3ConstructionTests(unittest.TestCase):
    def test_xyz(self):
        v = Vector3(1.0, 2.0, 3.0)
        self.assertEqual(v.x, 1.0)
        self.assertEqual(v.y, 2.0)
        self.assertEqual(v.z, 3.0)

    def test_copy(self):
        a = Vector3(1.0, -2.0, 0.5)
        b = Vector3(a)
        self.assertEqual(a, b)
        self.assertIsNot(a, b)

    def test_from_sequence(self):
        v = Vector3([4.0, 5.0, 6.0])
        self.assertEqual(v.as_tuple(), (4.0, 5.0, 6.0))

    def test_zero(self):
        v = Vector3()
        self.assertEqual(v, ZERO)

    def test_bad_arity(self):
        self.assertRaises(TypeError, Vector3, 1.0, 2.0)
        self.assertRaises(TypeError, Vector3, 1.0, 2.0, 3.0, 4.0)

    def test_bad_sequence(self):
        self.assertRaises(TypeError, Vector3, [1.0, 2.0])


class Vector3ArithmeticTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(Vector3(1, 2, 3) + Vector3(4, 5, 6), Vector3(5, 7, 9))

    def test_sub(self):
        self.assertEqual(Vector3(4, 5, 6) - Vector3(1, 2, 3), Vector3(3, 3, 3))

    def test_mul_scalar(self):
        self.assertEqual(Vector3(1, 2, 3) * 2.0, Vector3(2, 4, 6))
        self.assertEqual(2.0 * Vector3(1, 2, 3), Vector3(2, 4, 6))

    def test_mul_vector_is_dot(self):
        self.assertEqual(Vector3(1, 0, 0) * Vector3(0, 1, 0), 0.0)
        self.assertEqual(Vector3(2, 3, 4) * Vector3(1, 1, 1), 9.0)

    def test_div(self):
        self.assertEqual(Vector3(2, 4, 6) / 2.0, Vector3(1, 2, 3))

    def test_neg(self):
        self.assertEqual(-Vector3(1, -2, 3), Vector3(-1, 2, -3))


class Vector3GeometryTests(unittest.TestCase):
    def test_length(self):
        self.assertAlmostEqual(Vector3(3, 4, 0).length, 5.0)
        self.assertAlmostEqual(Vector3(1, 2, 2).length, 3.0)

    def test_dot(self):
        self.assertEqual(Vector3(1, 2, 3).dot(Vector3(4, 5, 6)), 32.0)

    def test_cross_right_hand(self):
        c = UNIT_Z.cross(Vector3(0, 1, 0))
        # Z cross Y = -X
        self.assertAlmostEqual(c.x, -1.0)
        self.assertAlmostEqual(c.y, 0.0)
        self.assertAlmostEqual(c.z, 0.0)

    def test_normalise(self):
        v = Vector3(0, 0, 5).normalized()
        self.assertAlmostEqual(v.length, 1.0)
        self.assertAlmostEqual(v.z, 1.0)

    def test_normalise_zero(self):
        v = Vector3(0, 0, 0)
        v.normalise()
        self.assertEqual(v, ZERO)

    def test_distance(self):
        self.assertAlmostEqual(Vector3(0, 0, 0).distanceTo(Vector3(0, 3, 4)), 5.0)

    def test_lerp(self):
        mid = Vector3(0, 0, 0).lerp(Vector3(2, 4, 6), 0.5)
        self.assertEqual(mid, Vector3(1, 2, 3))


class Vector3MiscTests(unittest.TestCase):
    def test_index(self):
        v = Vector3(7, 8, 9)
        self.assertEqual(v[0], 7)
        self.assertEqual(v[1], 8)
        self.assertEqual(v[2], 9)
        self.assertEqual(list(v), [7.0, 8.0, 9.0])

    def test_is_finite(self):
        self.assertTrue(Vector3(1, 2, 3).isFinite())
        self.assertFalse(Vector3(float('nan'), 0, 0).isFinite())
        self.assertFalse(Vector3(0, float('inf'), 0).isFinite())

    def test_hash_eq(self):
        a = Vector3(1, 2, 3)
        b = Vector3(1, 2, 3)
        self.assertEqual(hash(a), hash(b))
        self.assertEqual(len({a, b}), 1)


if __name__ == '__main__':
    unittest.main()
