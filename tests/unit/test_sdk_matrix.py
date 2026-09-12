# -*- coding: utf-8 -*-
"""SDK math.matrix 单元测试。"""
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

from sdk.math.matrix import Matrix, translationMatrix  # noqa: E402
from sdk.math.vector import Vector3  # noqa: E402


class MatrixConstructionTests(unittest.TestCase):
    def test_identity(self):
        m = Matrix()
        self.assertAlmostEqual(m.get(0, 0), 1.0)
        self.assertAlmostEqual(m.get(1, 1), 1.0)
        self.assertAlmostEqual(m.get(2, 2), 1.0)
        self.assertAlmostEqual(m.get(3, 3), 1.0)
        self.assertAlmostEqual(m.get(0, 3), 0.0)

    def test_copy(self):
        a = Matrix()
        a.setTranslate(1, 2, 3)
        b = Matrix(a)
        self.assertEqual(a, b)

    def test_from_sequence(self):
        flat = [
            1, 0, 0, 5,
            0, 1, 0, 6,
            0, 0, 1, 7,
            0, 0, 0, 1,
        ]
        m = Matrix(flat)
        self.assertEqual(m.translation, Vector3(5, 6, 7))

    def test_bad_length(self):
        self.assertRaises(TypeError, Matrix, [1, 2, 3])


class MatrixTranslationTests(unittest.TestCase):
    def test_apply_point(self):
        m = translationMatrix(10, 20, 30)
        p = m.applyPoint(Vector3(1, 2, 3))
        self.assertEqual(p, Vector3(11, 22, 33))

    def test_apply_vector_ignores_translation(self):
        m = translationMatrix(10, 20, 30)
        v = m.applyVector(Vector3(1, 0, 0))
        self.assertEqual(v, Vector3(1, 0, 0))

    def test_translation_property(self):
        m = Matrix()
        m.translation = Vector3(1, 2, 3)
        self.assertEqual(m.translation, Vector3(1, 2, 3))
        m.translation = (4, 5, 6)
        self.assertEqual(m.translation, Vector3(4, 5, 6))


class MatrixRotationTests(unittest.TestCase):
    def test_yaw_90(self):
        m = Matrix()
        m.setYawPitchRoll(math.pi / 2.0, 0.0, 0.0)
        # +Z 前向旋转到 +X
        fwd = m.applyVector(Vector3(0, 0, 1))
        self.assertAlmostEqual(fwd.x, 1.0, places=6)
        self.assertAlmostEqual(fwd.z, 0.0, places=6)
        self.assertAlmostEqual(m.yaw, math.pi / 2.0, places=6)

    def test_pitch(self):
        m = Matrix()
        # 抬炮（向上）在 BigWorld 车体习惯中 pitch 为负
        m.setYawPitchRoll(0.0, -math.pi / 6.0, 0.0)
        fwd = m.applyVector(Vector3(0, 0, 1))
        self.assertGreater(fwd.y, 0.0)
        self.assertAlmostEqual(m.pitch, -math.pi / 6.0, places=6)

    def test_roll(self):
        m = Matrix()
        m.setYawPitchRoll(0.0, 0.0, math.pi / 4.0)
        self.assertAlmostEqual(m.roll, math.pi / 4.0, places=6)

    def test_yaw_pitch_roundtrip(self):
        for yaw, pitch in (
            (0.0, 0.0),
            (0.3, -0.2),
            (-1.2, 0.5),
            (math.pi * 0.9, 0.0),
        ):
            m = Matrix()
            m.setYawPitchRoll(yaw, pitch, 0.0)
            self.assertAlmostEqual(m.yaw, yaw, places=6)
            self.assertAlmostEqual(m.pitch, pitch, places=6)


class MatrixComposeTests(unittest.TestCase):
    def test_mul_translation_rotation(self):
        rot = Matrix()
        rot.setYawPitchRoll(math.pi / 2.0, 0.0, 0.0)
        trans = translationMatrix(0, 0, 10)
        # 先旋转再平移：点 (0,0,1) -> 旋转到 (1,0,0) -> 平移 (1,0,10)
        combined = trans.applyMatrix(rot)
        p = combined.applyPoint(Vector3(0, 0, 1))
        self.assertAlmostEqual(p.x, 1.0, places=6)
        self.assertAlmostEqual(p.z, 10.0, places=6)

    def test_star_operator(self):
        a = translationMatrix(1, 0, 0)
        b = translationMatrix(0, 2, 0)
        c = a * b
        self.assertEqual(c.translation, Vector3(1, 2, 0))


if __name__ == '__main__':
    unittest.main()
