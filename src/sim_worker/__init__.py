# -*- coding: utf-8 -*-
"""sim-worker — 服务器权威模拟进程（Python 3）。

职责：
- 接受薄客户端 TCP 连接（JSON lines，复用 ``protocol`` 包）
- hello / 能力协商 / welcome 握手
- 房间与 roster 管理
- 30 Hz 世界 tick 与 15 Hz 快照广播
"""
from __future__ import absolute_import, division, print_function

__all__ = [
    'main',
    'server',
    'session',
    'tick',
    'room',
]
