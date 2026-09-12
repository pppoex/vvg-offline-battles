# -*- coding: utf-8 -*-
"""JSON lines 序列化 / 反序列化。

线上格式：UTF-8 JSON + ``\\n``，紧凑分隔符（与 0.9.22 一致）。
"""
from __future__ import absolute_import, division, print_function

import json

from protocol.constants import (
    JSONLINES_DELIMITER,
    JSONLINES_DELIMITER_TEXT,
    MAX_BUFFER_BYTES,
    MAX_MESSAGE_BYTES,
)
from protocol.messages import ProtocolError, message_type_of


class SerializerError(ValueError):
    """编码 / 解码失败。"""


def _dumps(message):
    if not isinstance(message, dict):
        raise SerializerError('message must be a dict')
    kind = message_type_of(message)
    if kind is None or 'type' not in message:
        raise SerializerError('message.type is required')
    try:
        # ensure_ascii 保持 Py2/3 一致的纯 ASCII 转义
        return json.dumps(
            message, separators=(',', ':'), ensure_ascii=True,
            allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SerializerError('json encode failed: %s' % exc)


def encode_message(message, with_delimiter=True):
    """dict → wire bytes（UTF-8，默认带换行）。

    长度超过 MAX_MESSAGE_BYTES 时抛 SerializerError。
    """
    text = _dumps(message)
    if with_delimiter:
        text = text + JSONLINES_DELIMITER_TEXT
    try:
        payload = text.encode('utf-8')
    except UnicodeEncodeError as exc:
        raise SerializerError('utf-8 encode failed: %s' % exc)
    # 不含 delimiter 时上限按 MAX；含 delimiter 时按 MAX+1
    limit = MAX_MESSAGE_BYTES + (1 if with_delimiter else 0)
    if len(payload) > limit:
        raise SerializerError(
            'message exceeds MAX_MESSAGE_BYTES (%d > %d)' % (
                len(payload), limit))
    return payload


def decode_message(line):
    """一行文本 / bytes → dict。

    接受 str/bytes/unicode；忽略首尾空白与可选换行。
    失败抛 SerializerError。
    """
    if line is None:
        raise SerializerError('line is None')
    if isinstance(line, bytes):
        try:
            line = line.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise SerializerError('utf-8 decode failed: %s' % exc)
    if not isinstance(line, (str, bytes)):
        try:
            if not isinstance(line, unicode):  # noqa: F821
                raise SerializerError('line must be text')
        except NameError:
            raise SerializerError('line must be text')
    text = line.strip()
    if not text:
        raise SerializerError('empty line')
    if len(text) > MAX_MESSAGE_BYTES:
        raise SerializerError('line exceeds MAX_MESSAGE_BYTES')
    try:
        message = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise SerializerError('json decode failed: %s' % exc)
    if not isinstance(message, dict):
        raise SerializerError('decoded value must be a JSON object')
    kind = message_type_of(message)
    if not kind:
        raise SerializerError('decoded message missing type')
    return message


def try_decode_message(line):
    """失败返回 None，不抛异常。"""
    try:
        return decode_message(line)
    except SerializerError:
        return None


class LineDecoder(object):
    """粘包 / 半包友好的 JSON lines 增量解码器。

    用法::

        decoder = LineDecoder()
        for chunk in chunks:
            for message in decoder.feed(chunk):
                handle(message)
    """

    def __init__(self, max_buffer_bytes=None):
        self._buffer = u''
        self._max_buffer = (
            MAX_BUFFER_BYTES if max_buffer_bytes is None
            else int(max_buffer_bytes))
        self._overflow = False

    def reset(self):
        self._buffer = u''
        self._overflow = False

    @property
    def overflow(self):
        return self._overflow

    def pending_bytes(self):
        try:
            return len(self._buffer.encode('utf-8'))
        except UnicodeEncodeError:
            return len(self._buffer)

    def feed(self, chunk):
        """喂入 bytes 或文本；返回完整消息 dict 列表。

        超缓冲时置 overflow 并返回已解出的消息（调用方应断开）。
        解码失败的行被静默跳过（与参考客户端一致）。
        """
        if self._overflow:
            return []
        if chunk is None:
            return []
        if isinstance(chunk, bytes):
            try:
                text = chunk.decode('utf-8')
            except UnicodeDecodeError:
                self._overflow = True
                return []
        else:
            text = chunk

        self._buffer += text
        if len(self._buffer) > self._max_buffer:
            self._overflow = True
            self._buffer = u''
            return []

        messages = []
        while True:
            index = self._buffer.find(JSONLINES_DELIMITER_TEXT)
            if index < 0:
                break
            line = self._buffer[:index]
            self._buffer = self._buffer[index + 1:]
            if not line.strip():
                continue
            message = try_decode_message(line)
            if message is not None:
                messages.append(message)
        return messages

    def flush(self):
        """连接关闭时取出残余半行（若非空则尝试解码）。"""
        if self._overflow:
            self._buffer = u''
            return []
        leftover = self._buffer
        self._buffer = u''
        if not leftover.strip():
            return []
        message = try_decode_message(leftover)
        return [message] if message is not None else []


def encode_lines(messages):
    """批量编码为单个 bytes 块（每条一行）。"""
    parts = []
    total = 0
    for message in messages:
        payload = encode_message(message, with_delimiter=True)
        total += len(payload)
        if total > MAX_MESSAGE_BYTES * 4:
            raise SerializerError('batch exceeds outbound limit')
        parts.append(payload)
    return b''.join(parts)


# 重导出，方便调用方
__all__ = [
    'SerializerError',
    'ProtocolError',
    'encode_message',
    'decode_message',
    'try_decode_message',
    'encode_lines',
    'LineDecoder',
    'JSONLINES_DELIMITER',
    'MAX_MESSAGE_BYTES',
]
