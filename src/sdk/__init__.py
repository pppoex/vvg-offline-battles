# -*- coding: utf-8 -*-
"""vvg SDK — 版本无关的可复用基础模块。

客户端运行时为 Python 2.7（仅标准库）；服务器 / 测试为 Python 3。
本包内代码须保持 2/3 兼容：不使用 f-string、类型注解、dataclass 等 Py3 专属特性。
"""
from __future__ import absolute_import, division, print_function

__all__ = ['config', 'hooks', 'log', 'math']

__version__ = '0.1.0'
