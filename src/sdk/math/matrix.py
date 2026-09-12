# -*- coding: utf-8 -*-
"""矩阵运算 — 替代 BigWorld Math.Matrix（4x4，行主序存储）。

与 BigWorld 用法对齐的接口：
- ``Matrix()`` 单位阵；``Matrix(other)`` 从 Matrix 或 16 元序列复制
- ``.translation`` — Vector3 读写（仅平移分量）
- ``.yaw`` / ``.pitch`` / ``.roll`` — 从旋转部分提取欧拉角（弧度）
- ``setYawPitchRoll`` / ``setTranslate`` / ``identity``
- ``applyPoint`` / ``applyVector``

坐标系：右手，Y-up；yaw 绕 Y，pitch 绕 X，roll 绕 Z。
欧拉角顺序：yaw → pitch → roll（内旋），与 BigWorld 车体习惯一致。
"""
from __future__ import absolute_import, division, print_function

import math as _math

from .vector import Vector3

_EPS = 1e-12


class Matrix(object):
    """4x4 仿射矩阵。内部 m00..m33 按行主序，a 为 16 元 tuple。"""

    __slots__ = ('_m',)

    def __init__(self, *args):
        n = len(args)
        if n == 0:
            self._m = _identity_tuple()
        elif n == 1:
            other = args[0]
            if isinstance(other, Matrix):
                self._m = other._m
            else:
                seq = tuple(float(v) for v in other)
                if len(seq) != 16:
                    raise TypeError('Matrix expects 16 elements, got %d' % len(seq))
                self._m = seq
        else:
            raise TypeError('Matrix() takes 0 or 1 args, got %d' % n)

    # -- 构造辅助 ---------------------------------------------------------

    @staticmethod
    def identity():
        return Matrix()

    @staticmethod
    def translate(x, y, z):
        m = Matrix()
        m.setTranslate(x, y, z)
        return m

    @staticmethod
    def fromRows(rows):
        """rows: 4 个长度为 4 的序列（行主序）。"""
        flat = []
        for row in rows:
            flat.extend(float(v) for v in row)
        if len(flat) != 16:
            raise TypeError('fromRows needs 4x4 elements')
        return Matrix(flat)

    # -- 内部索引 ---------------------------------------------------------

    def _idx(self, row, col):
        return row * 4 + col

    def get(self, row, col):
        return self._m[self._idx(row, col)]

    def set(self, row, col, value):
        m = list(self._m)
        m[self._idx(row, col)] = float(value)
        self._m = tuple(m)

    def as_tuple(self):
        return self._m

    def as_list(self):
        return list(self._m)

    def copy(self):
        return Matrix(self)

    def identity_inplace(self):
        self._m = _identity_tuple()
        return self

    # -- 平移 -------------------------------------------------------------

    @property
    def translation(self):
        m = self._m
        return Vector3(m[3], m[7], m[11])

    @translation.setter
    def translation(self, value):
        v = Vector3(value)
        m = list(self._m)
        m[3] = v.x
        m[7] = v.y
        m[11] = v.z
        self._m = tuple(m)

    def setTranslate(self, x, y, z):
        m = list(self._m)
        m[3] = float(x)
        m[7] = float(y)
        m[11] = float(z)
        self._m = tuple(m)

    def preTranslate(self, x, y, z):
        """在本地空间前乘平移：T * M。"""
        t = Matrix.translate(x, y, z)
        self._m = _mat_mul(t._m, self._m)
        return self

    def postTranslate(self, x, y, z):
        """在世界空间右乘平移：M * T。"""
        t = Matrix.translate(x, y, z)
        self._m = _mat_mul(self._m, t._m)
        return self

    # -- 欧拉角 -------------------------------------------------------------

    @property
    def yaw(self):
        """绕 Y 轴偏航（弧度）。取对象 +Z 前向在 XZ 平面的方位。"""
        m = self._m
        # 旋转部分第三列 = 对象 +Z 在世界系下的方向 (fx, fy, fz)
        return _math.atan2(m[2], m[10])

    @property
    def pitch(self):
        """俯仰（弧度），向上抬炮为负（forward.y 为正时 pitch 为负）。"""
        m = self._m
        fy = max(-1.0, min(1.0, m[6]))
        return _math.asin(-fy)

    @property
    def roll(self):
        """横滚（弧度）。"""
        m = self._m
        # R = Ry*Rx*Rz 下 r10=cp*sr, r11=cp*cr
        return _math.atan2(m[4], m[5])

    def setYawPitchRoll(self, yaw, pitch, roll=0.0):
        """按 yaw→pitch→roll 设置旋转，保留当前平移。"""
        cy, sy = _math.cos(yaw), _math.sin(yaw)
        cp, sp = _math.cos(pitch), _math.sin(pitch)
        cr, sr = _math.cos(roll), _math.sin(roll)

        # R = Ry * Rx * Rz（行主序）
        # Ry
        #  cy  0  sy
        #   0  1   0
        # -sy  0  cy
        # Rx
        #  1   0   0
        #  0  cp -sp
        #  0  sp  cp
        # Rz
        # cr -sr  0
        # sr  cr  0
        #  0   0  1
        r00 = cy * cr + sy * sp * sr
        r01 = -cy * sr + sy * sp * cr
        r02 = sy * cp
        r10 = cp * sr
        r11 = cp * cr
        r12 = -sp
        r20 = -sy * cr + cy * sp * sr
        r21 = sy * sr + cy * sp * cr
        r22 = cy * cp

        m = list(self._m)
        m[0], m[1], m[2] = r00, r01, r02
        m[4], m[5], m[6] = r10, r11, r12
        m[8], m[9], m[10] = r20, r21, r22
        self._m = tuple(m)
        return self

    def setRotationAxis(self, axis, angle):
        """绕任意轴（Rodrigues）。axis 会被归一化。"""
        a = Vector3(axis).normalized()
        if a.lengthSquared < _EPS:
            self.identity_inplace()
            return self
        x, y, z = a.x, a.y, a.z
        c, s = _math.cos(angle), _math.sin(angle)
        t = 1.0 - c
        r = [
            t * x * x + c,     t * x * y - s * z, t * x * z + s * y, 0.0,
            t * x * y + s * z, t * y * y + c,     t * y * z - s * x, 0.0,
            t * x * z - s * y, t * y * z + s * x, t * z * z + c,     0.0,
            0.0,               0.0,               0.0,               1.0,
        ]
        # 保留平移
        m = list(self._m)
        m[0:3] = r[0:3]
        m[4:7] = r[4:7]
        m[8:11] = r[8:11]
        # r[3,7,11] 是 0，不覆盖平移
        self._m = tuple(m)
        return self

    # -- 变换 -------------------------------------------------------------

    def applyPoint(self, point):
        """完整变换点（含平移）。"""
        p = Vector3(point)
        m = self._m
        return Vector3(
            m[0] * p.x + m[1] * p.y + m[2] * p.z + m[3],
            m[4] * p.x + m[5] * p.y + m[6] * p.z + m[7],
            m[8] * p.x + m[9] * p.y + m[10] * p.z + m[11],
        )

    def applyVector(self, vector):
        """仅旋转/缩放，不含平移。"""
        p = Vector3(vector)
        m = self._m
        return Vector3(
            m[0] * p.x + m[1] * p.y + m[2] * p.z,
            m[4] * p.x + m[5] * p.y + m[6] * p.z,
            m[8] * p.x + m[9] * p.y + m[10] * p.z,
        )

    def applyMatrix(self, other):
        """self * other（other 先作用）。返回新 Matrix。"""
        o = Matrix(other)
        return Matrix(_mat_mul(self._m, o._m))

    def __mul__(self, other):
        if isinstance(other, Matrix):
            return self.applyMatrix(other)
        if isinstance(other, Vector3):
            return self.applyPoint(other)
        return NotImplemented

    def __eq__(self, other):
        if not isinstance(other, Matrix):
            try:
                other = Matrix(other)
            except Exception:
                return NotImplemented
        for a, b in zip(self._m, other._m):
            if abs(a - b) > 1e-9:
                return False
        return True

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __repr__(self):
        m = self._m
        rows = (
            '[%8.4f %8.4f %8.4f %8.4f]' % m[0:4],
            '[%8.4f %8.4f %8.4f %8.4f]' % m[4:8],
            '[%8.4f %8.4f %8.4f %8.4f]' % m[8:12],
            '[%8.4f %8.4f %8.4f %8.4f]' % m[12:16],
        )
        return 'Matrix(\n  %s\n  %s\n  %s\n  %s\n)' % rows

    def almostEqual(self, other, places=6):
        try:
            o = Matrix(other)
        except Exception:
            return False
        tol = 10.0 ** (-places)
        for a, b in zip(self._m, o._m):
            if abs(a - b) > tol:
                return False
        return True


def _identity_tuple():
    return (
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    )


def _mat_mul(a, b):
    """两个行主序 16 元 tuple 相乘 a*b。"""
    out = [0.0] * 16
    for row in range(4):
        ar = row * 4
        for col in range(4):
            s = 0.0
            for k in range(4):
                s += a[ar + k] * b[k * 4 + col]
            out[ar + col] = s
    return tuple(out)


def rotationYaw(pitch, yaw, roll=0.0):
    """便捷：仅旋转矩阵。"""
    m = Matrix()
    m.setYawPitchRoll(yaw, pitch, roll)
    return m


def translationMatrix(x, y, z):
    return Matrix.translate(x, y, z)
