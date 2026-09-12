# -*- coding: utf-8 -*-
"""向量运算 — 替代 BigWorld Math.Vector3（sim-worker / 预测层用）。

坐标系约定与 BigWorld 车体一致：右手系，Y 向上，车头默认 +Z。
"""
from __future__ import absolute_import, division, print_function

import math as _math


class Vector3(object):
    """三维向量。支持：

    - 构造：``Vector3(x, y, z)`` / ``Vector3(other)`` / ``Vector3(seq)``
    - 分量：``.x`` ``.y`` ``.z``
    - 运算：``+`` ``-`` ``*``（标量或点积语义见 doc）``/`` 一元 ``-``
    - 点积 ``dot``、叉积 ``cross``、``length`` ``normalise`` ``normalized``
    """

    __slots__ = ('x', 'y', 'z')

    def __init__(self, *args):
        n = len(args)
        if n == 3:
            self.x = float(args[0])
            self.y = float(args[1])
            self.z = float(args[2])
        elif n == 1:
            other = args[0]
            if isinstance(other, Vector3):
                self.x = other.x
                self.y = other.y
                self.z = other.z
            else:
                seq = tuple(other)
                if len(seq) != 3:
                    raise TypeError('Vector3 expects 3 components, got %r' % (seq,))
                self.x = float(seq[0])
                self.y = float(seq[1])
                self.z = float(seq[2])
        elif n == 0:
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
        else:
            raise TypeError('Vector3() takes 0 or 1 or 3 args, got %d' % n)

    # -- 基本属性 ---------------------------------------------------------

    @property
    def length(self):
        return _math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    @property
    def lengthSquared(self):
        return self.x * self.x + self.y * self.y + self.z * self.z

    # BigWorld 有时用扁平名
    lengthSqr = lengthSquared

    def get(self):
        return (self.x, self.y, self.z)

    def set(self, x, y, z):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def copy(self):
        return Vector3(self)

    def as_tuple(self):
        return (self.x, self.y, self.z)

    # -- 运算 -------------------------------------------------------------

    def __add__(self, other):
        o = Vector3(other)
        return Vector3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, other):
        o = Vector3(other)
        return Vector3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, other):
        if isinstance(other, Vector3):
            # 点积（与 BigWorld `*` 语义对齐：两向量时返回标量）
            return self.dot(other)
        return Vector3(self.x * other, self.y * other, self.z * other)

    def __rmul__(self, other):
        if isinstance(other, Vector3):
            return other.dot(self)
        return Vector3(self.x * other, self.y * other, self.z * other)

    def __div__(self, scalar):  # Py2
        s = float(scalar)
        return Vector3(self.x / s, self.y / s, self.z / s)

    def __truediv__(self, scalar):  # Py3
        s = float(scalar)
        return Vector3(self.x / s, self.y / s, self.z / s)

    def __neg__(self):
        return Vector3(-self.x, -self.y, -self.z)

    def __pos__(self):
        return Vector3(self)

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __len__(self):
        return 3

    def __getitem__(self, index):
        if index == 0 or index == -3:
            return self.x
        if index == 1 or index == -2:
            return self.y
        if index == 2 or index == -1:
            return self.z
        raise IndexError('Vector3 index out of range: %r' % (index,))

    def __eq__(self, other):
        if not isinstance(other, Vector3):
            try:
                other = Vector3(other)
            except Exception:
                return NotImplemented
        return (self.x == other.x and self.y == other.y and self.z == other.z)

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        return hash((self.x, self.y, self.z))

    def __repr__(self):
        return 'Vector3(%.6g, %.6g, %.6g)' % (self.x, self.y, self.z)

    # -- 向量方法 ---------------------------------------------------------

    def dot(self, other):
        o = Vector3(other)
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, other):
        o = Vector3(other)
        return Vector3(
            self.y * o.z - self.z * o.y,
            self.z * o.x - self.x * o.z,
            self.x * o.y - self.y * o.x,
        )

    def normalise(self):
        """原地归一化；零向量保持不变。返回 self。"""
        length = self.length
        if length > 0.0:
            inv = 1.0 / length
            self.x *= inv
            self.y *= inv
            self.z *= inv
        return self

    def normalized(self):
        """返回归一化后的新向量。"""
        return self.copy().normalise()

    # 拼写兼容
    normalize = normalise

    def distanceTo(self, other):
        return (self - other).length

    def distanceToSquared(self, other):
        return (self - other).lengthSquared

    def lerp(self, other, t):
        """线性插值到 other，t∈[0,1]。返回新向量。"""
        o = Vector3(other)
        u = float(t)
        return Vector3(
            self.x + (o.x - self.x) * u,
            self.y + (o.y - self.y) * u,
            self.z + (o.z - self.z) * u,
        )

    def isFinite(self):
        for value in (self.x, self.y, self.z):
            if value != value or value in (float('inf'), float('-inf')):
                return False
        return True


ZERO = Vector3(0.0, 0.0, 0.0)
UNIT_X = Vector3(1.0, 0.0, 0.0)
UNIT_Y = Vector3(0.0, 1.0, 0.0)
UNIT_Z = Vector3(0.0, 0.0, 1.0)
