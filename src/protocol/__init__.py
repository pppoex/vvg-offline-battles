# -*- coding: utf-8 -*-
"""vvg 协议层 — JSON lines over TCP，客户端 / 服务器 / sim-worker 共用。

Python 2/3 双兼容：禁止 f-string、运行时类型注解、dataclass。
与 0.9.22 参考项目 v5 协议对齐；默认端口与 ``sdk.config`` 一致。
"""
from __future__ import absolute_import, division, print_function

from protocol.constants import (
    CLIENT_BUILD,
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
    JSONLINES_DELIMITER,
    MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
)
from protocol.serializer import (
    decode_message,
    encode_message,
    LineDecoder,
)

__all__ = [
    'CLIENT_BUILD',
    'DEFAULT_SERVER_HOST',
    'DEFAULT_SERVER_PORT',
    'JSONLINES_DELIMITER',
    'MAX_MESSAGE_BYTES',
    'PROTOCOL_VERSION',
    'decode_message',
    'encode_message',
    'LineDecoder',
    'capabilities',
    'constants',
    'messages',
    'serializer',
]
