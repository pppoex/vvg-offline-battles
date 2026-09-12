# -*- coding: utf-8 -*-
"""Thin client for vvg-offline-battles (M4).

Python 2/3 dual-compatible package (client runtime is 2.7 stdlib-only).
Host unit / integration tests run under Python 3 with ``src`` and
``src/client`` on ``sys.path``.
"""
from __future__ import absolute_import, division, print_function

__all__ = [
    'bootstrap',
    'session',
    'network',
    'prediction',
    'hooks',
]

__version__ = '0.1.0'
