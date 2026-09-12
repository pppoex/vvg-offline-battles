# -*- coding: utf-8 -*-
"""序列化器专项单元测试（与 test_protocol 分离，聚焦 wire 层）。"""
from __future__ import absolute_import, division, print_function

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from protocol import constants as C  # noqa: E402
from protocol.messages import build_hello, build_input  # noqa: E402
from protocol.serializer import (  # noqa: E402
    LineDecoder,
    SerializerError,
    decode_message,
    encode_lines,
    encode_message,
    try_decode_message,
)


class EncodeShapeTests(unittest.TestCase):
    def test_delimiter_is_single_lf(self):
        payload = encode_message({'type': C.MSG_LEAVE})
        self.assertTrue(payload.endswith(b'\n'))
        self.assertFalse(payload.endswith(b'\n\n'))
        # body 不含换行
        self.assertEqual(payload.count(b'\n'), 1)

    def test_without_delimiter(self):
        payload = encode_message(
            {'type': C.MSG_LEAVE}, with_delimiter=False)
        self.assertFalse(payload.endswith(b'\n'))

    def test_protocol_field_present(self):
        message = build_hello('A', 'v')
        self.assertIn(b'"protocol":5', encode_message(message))


class InputWireTests(unittest.TestCase):
    def test_input_round_trip_with_pose(self):
        original = build_input(
            12, 0.1, -0.2,
            aim_yaw=3.14, gun_pitch=-0.4,
            input_seq=99,
            position=(10.0, 0.0, -20.0),
            yaw=1.5, pitch=0.05, roll=-0.02,
            speed=12.5, fire_seq=3,
        )
        decoded = decode_message(encode_message(original))
        self.assertEqual(decoded, original)
        self.assertEqual(decoded['input_seq'], 99)
        self.assertEqual(decoded['fire_seq'], 3)


class BatchTests(unittest.TestCase):
    def test_encode_lines(self):
        block = encode_lines([
            {'type': C.MSG_LEAVE},
            {'type': C.MSG_PING, 'seq': 1, 'client_time': 0.0},
        ])
        self.assertEqual(block.count(b'\n'), 2)
        decoder = LineDecoder()
        messages = decoder.feed(block)
        self.assertEqual(
            [m['type'] for m in messages],
            [C.MSG_LEAVE, C.MSG_PING])


class TryDecodeTests(unittest.TestCase):
    def test_try_decode_none_on_error(self):
        self.assertIsNone(try_decode_message('{'))
        self.assertIsNone(try_decode_message(None))
        decoded = try_decode_message(
            encode_message({'type': C.MSG_LEAVE}).decode('utf-8'))
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded['type'], C.MSG_LEAVE)


class NestedPayloadTests(unittest.TestCase):
    def test_snapshot_like_nested_dict(self):
        message = {
            'type': C.MSG_SNAPSHOT,
            'protocol': C.PROTOCOL_VERSION,
            'round_id': 3,
            'server_tick': 10,
            'server_time_ms': 333,
            'payload': {
                'vehicles': [
                    {'id': 1, 'x': 1.0, 'y': 2.0, 'z': 3.0},
                    {'id': 2, 'x': -1.0, 'y': 0.0, 'z': 0.5},
                ],
            },
        }
        decoded = decode_message(encode_message(message))
        self.assertEqual(decoded['payload']['vehicles'][1]['id'], 2)


if __name__ == '__main__':
    unittest.main()
