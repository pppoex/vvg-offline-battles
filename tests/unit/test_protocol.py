# -*- coding: utf-8 -*-
"""协议消息与能力协商单元测试。"""
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
from protocol.capabilities import (  # noqa: E402
    CAP_CORE_SESSION_V1,
    CapabilityError,
    DEFAULT_CLIENT_CAPABILITIES,
    DEFAULT_SERVER_CAPABILITIES,
    contains_required,
    intersect,
    negotiate,
    normalize_capabilities,
)
from protocol.messages import (  # noqa: E402
    ProtocolError,
    build_battle_live,
    build_battle_ready,
    build_battle_start,
    build_error,
    build_events,
    build_hello,
    build_input,
    build_leave,
    build_leave_battle,
    build_ping,
    build_pong,
    build_roster,
    build_select_team,
    build_select_vehicle,
    build_snapshot,
    build_start_battle,
    build_team_denied,
    build_welcome,
    is_ordered_receive,
    is_state_barrier,
    message_type_of,
    validate_message,
)
from protocol.serializer import (  # noqa: E402
    LineDecoder,
    SerializerError,
    decode_message,
    encode_message,
)


class ConstantsTests(unittest.TestCase):
    def test_protocol_version_matches_sdk(self):
        sdk_path = os.path.join(SRC, 'sdk')
        if sdk_path not in sys.path:
            sys.path.insert(0, sdk_path)
        from sdk import config as sdk_config
        self.assertEqual(C.PROTOCOL_VERSION, sdk_config.PROTOCOL_VERSION)

    def test_default_port_matches_sdk(self):
        self.assertEqual(C.DEFAULT_SERVER_PORT, 28782)
        self.assertEqual(C.DEFAULT_SERVER_HOST, '127.0.0.1')

    def test_type_sets_disjoint_by_direction(self):
        self.assertIn(C.MSG_HELLO, C.CLIENT_TO_SERVER_TYPES)
        self.assertIn(C.MSG_WELCOME, C.SERVER_TO_CLIENT_TYPES)
        self.assertNotIn(C.MSG_HELLO, C.SERVER_TO_CLIENT_TYPES)
        self.assertNotIn(C.MSG_WELCOME, C.CLIENT_TO_SERVER_TYPES)


class CapabilityTests(unittest.TestCase):
    def test_normalize_dedupes_and_preserves_order(self):
        result = normalize_capabilities(['b', 'a', 'b', 'c'])
        self.assertEqual(result, ['b', 'a', 'c'])

    def test_normalize_rejects_bad_names(self):
        with self.assertRaises(CapabilityError):
            normalize_capabilities([123])
        with self.assertRaises(CapabilityError):
            normalize_capabilities([''])
        with self.assertRaises(CapabilityError):
            normalize_capabilities(['x' * 65])

    def test_normalize_rejects_too_many(self):
        caps = ['c%02d' % i for i in range(33)]
        with self.assertRaises(CapabilityError):
            normalize_capabilities(caps)

    def test_contains_required(self):
        self.assertTrue(contains_required(DEFAULT_CLIENT_CAPABILITIES))
        self.assertFalse(contains_required(['other']))

    def test_intersect(self):
        self.assertEqual(
            intersect(['a', 'b', 'c'], ['c', 'b']),
            ['b', 'c'])

    def test_negotiate_ok(self):
        result = negotiate(
            DEFAULT_CLIENT_CAPABILITIES,
            DEFAULT_SERVER_CAPABILITIES)
        self.assertTrue(result['ok'])
        self.assertEqual(result['missing'], [])
        self.assertIn(CAP_CORE_SESSION_V1, result['shared'])

    def test_negotiate_missing_required(self):
        result = negotiate(['nope'], DEFAULT_SERVER_CAPABILITIES)
        self.assertFalse(result['ok'])
        self.assertEqual(result['missing'], [CAP_CORE_SESSION_V1])


class HelloMessageTests(unittest.TestCase):
    def test_player_hello_defaults(self):
        message = build_hello('Alice', 'ussr:R05_LT')
        self.assertEqual(message['type'], C.MSG_HELLO)
        self.assertEqual(message['protocol'], C.PROTOCOL_VERSION)
        self.assertEqual(message['role'], C.ROLE_PLAYER)
        self.assertEqual(message['name'], 'Alice')
        self.assertEqual(message['vehicle'], 'ussr:R05_LT')
        self.assertIn(CAP_CORE_SESSION_V1, message['capabilities'])
        self.assertEqual(message['capabilities'],
                         list(DEFAULT_CLIENT_CAPABILITIES))

    def test_player_hello_requires_identity(self):
        with self.assertRaises(ProtocolError):
            build_hello('', 'ussr:R05_LT')
        with self.assertRaises(ProtocolError):
            build_hello('Alice', '')

    def test_worker_hello_has_no_vehicle(self):
        message = build_hello(None, None, role=C.ROLE_WORKER)
        self.assertEqual(message['role'], C.ROLE_WORKER)
        self.assertNotIn('vehicle', message)
        self.assertNotIn('name', message)

    def test_worker_hello_rejects_bad_role(self):
        with self.assertRaises(ProtocolError):
            build_hello('a', 'v', role='ghost')

    def test_requested_team_bounds(self):
        message = build_hello('A', 'v', requested_team=2)
        self.assertEqual(message['requested_team'], 2)
        with self.assertRaises(ProtocolError):
            build_hello('A', 'v', requested_team=3)


class ControlMessageTests(unittest.TestCase):
    def test_leave(self):
        self.assertEqual(build_leave()['type'], C.MSG_LEAVE)

    def test_leave_battle(self):
        message = build_leave_battle(7)
        self.assertEqual(message['type'], C.MSG_LEAVE_BATTLE)
        self.assertEqual(message['round_id'], 7)

    def test_start_battle_with_duration(self):
        message = build_start_battle(0, requested_round_seconds=900)
        self.assertEqual(message['round_seconds'], 900)
        with self.assertRaises(ProtocolError):
            build_start_battle(0, requested_round_seconds=10)

    def test_select_vehicle_and_team(self):
        vehicle = build_select_vehicle('germany:G54_E-50', max_health=1750)
        self.assertEqual(vehicle['max_health'], 1750)
        self.assertEqual(build_select_team(1)['team'], 1)
        self.assertEqual(build_select_team(0)['team'], 0)
        with self.assertRaises(ProtocolError):
            build_select_team(9)

    def test_battle_ready(self):
        self.assertEqual(build_battle_ready(3)['round_id'], 3)

    def test_ping_pong(self):
        ping = build_ping(1, 12.5)
        self.assertEqual(ping['type'], C.MSG_PING)
        self.assertEqual(ping['seq'], 1)
        pong = build_pong(1, client_time=12.5, server_time=13.0)
        self.assertEqual(pong['type'], C.MSG_PONG)
        self.assertEqual(pong['server_time'], 13.0)


class InputMessageTests(unittest.TestCase):
    def test_basic_input(self):
        message = build_input(5, 0.5, -0.25, aim_yaw=1.2, gun_pitch=-0.1)
        self.assertEqual(message['type'], C.MSG_INPUT)
        self.assertEqual(message['forward'], 0.5)
        self.assertEqual(message['turn'], -0.25)
        self.assertEqual(message['input_seq'], 0)

    def test_unit_clamp(self):
        message = build_input(1, 5.0, -9.0)
        self.assertEqual(message['forward'], 1.0)
        self.assertEqual(message['turn'], -1.0)

    def test_position_bounds(self):
        message = build_input(
            1, 0.0, 0.0, position=(100.0, 0.0, -100.0))
        self.assertEqual(message['position'], [100.0, 0.0, -100.0])
        with self.assertRaises(ProtocolError):
            build_input(1, 0.0, 0.0, position=(99999.0, 0.0, 0.0))

    def test_gun_pitch_limit(self):
        with self.assertRaises(ProtocolError):
            build_input(1, 0.0, 0.0, gun_pitch=2.0)


class ServerMessageTests(unittest.TestCase):
    def test_welcome_core_fields(self):
        message = build_welcome(
            player_id=1,
            name='Alice',
            vehicle='ussr:R05_LT',
            team=1,
            map_name='01_karelia',
            phase=C.PHASE_WAITING,
            host_player_id=1,
            capabilities=DEFAULT_CLIENT_CAPABILITIES,
            server_capabilities=DEFAULT_SERVER_CAPABILITIES,
            spawn={'x': 1.0, 'y': 2.0, 'z': 3.0, 'yaw': 0.5},
        )
        self.assertEqual(message['type'], C.MSG_WELCOME)
        self.assertEqual(message['player_id'], 1)
        self.assertEqual(message['spawn']['z'], 3.0)
        self.assertIn(CAP_CORE_SESSION_V1, message['server_capabilities'])

    def test_welcome_invalid_phase(self):
        with self.assertRaises(ProtocolError):
            build_welcome(
                1, 'A', 'v', 1, 'map', 'sideways')

    def test_roster_and_battle_flow(self):
        roster = build_roster(
            C.PHASE_WAITING, 0, 1, '01_karelia',
            players=[{'id': 1, 'name': 'Alice'}],
            host_player_id=1,
            team_size=15,
        )
        self.assertEqual(roster['type'], C.MSG_ROSTER)
        start = build_battle_start(1, '01_karelia', state_revision=2)
        self.assertEqual(start['type'], C.MSG_BATTLE_START)
        live = build_battle_live(
            1, server_tick=0, state_revision=3, countdown_seconds=10.0)
        self.assertEqual(live['type'], C.MSG_BATTLE_LIVE)
        self.assertEqual(live['countdown_seconds'], 10.0)

    def test_snapshot_and_events(self):
        snap = build_snapshot(4, 10, 333, payload={'vehicles': []})
        self.assertEqual(snap['payload'], {'vehicles': []})
        events = build_events(4, [{'kind': 'shot'}], server_time_ms=400)
        self.assertEqual(events['events'][0]['kind'], 'shot')

    def test_error_and_denied(self):
        error = build_error(C.ERROR_PROTOCOL_MISMATCH, 'protocol mismatch')
        self.assertEqual(error['code'], 'protocol')
        denied = build_team_denied(2, 'team_full')
        self.assertEqual(denied['team'], 2)
        with self.assertRaises(ProtocolError):
            build_team_denied(5, 'x')


class ValidateTests(unittest.TestCase):
    def test_validate_and_type_of(self):
        message = build_hello('A', 'v')
        self.assertEqual(validate_message(message), C.MSG_HELLO)
        self.assertEqual(message_type_of(message), C.MSG_HELLO)
        self.assertIsNone(message_type_of({'no': 'type'}))

    def test_state_barrier_flags(self):
        self.assertTrue(is_state_barrier(build_welcome(
            1, 'A', 'v', 1, 'm', C.PHASE_WAITING)))
        self.assertTrue(is_ordered_receive(build_pong(1)))
        self.assertFalse(is_state_barrier(build_input(1, 0, 0)))


class SerializerRoundTripTests(unittest.TestCase):
    def test_hello_round_trip(self):
        original = build_hello('Alice', 'ussr:R05_LT')
        payload = encode_message(original)
        self.assertTrue(payload.endswith(b'\n'))
        decoded = decode_message(payload)
        self.assertEqual(decoded, original)

    def test_compact_no_spaces(self):
        payload = encode_message(build_leave())
        self.assertNotIn(b', ', payload)
        self.assertNotIn(b'": ', payload)

    def test_reject_nan(self):
        with self.assertRaises(SerializerError):
            encode_message({
                'type': C.MSG_PING,
                'seq': 1,
                'client_time': float('nan'),
            })

    def test_reject_non_dict(self):
        with self.assertRaises(SerializerError):
            encode_message(['not', 'a', 'dict'])
        with self.assertRaises(SerializerError):
            decode_message('[1,2,3]')
        with self.assertRaises(SerializerError):
            decode_message('')
        with self.assertRaises(SerializerError):
            decode_message('{"no_type":1}')

    def test_decode_accepts_bytes_and_str(self):
        original = build_pong(9, server_time=1.0)
        payload = encode_message(original)
        self.assertEqual(decode_message(payload), original)
        self.assertEqual(decode_message(payload.decode('utf-8')), original)

    def test_unicode_name_round_trip(self):
        original = build_hello(u'坦克手', 'ussr:R05_LT')
        decoded = decode_message(encode_message(original))
        self.assertEqual(decoded['name'], u'坦克手')

    def test_oversized_message_rejected(self):
        huge = build_hello('A', 'v')
        huge['pad'] = 'x' * (C.MAX_MESSAGE_BYTES + 10)
        with self.assertRaises(SerializerError):
            encode_message(huge)


class LineDecoderTests(unittest.TestCase):
    def test_single_line(self):
        decoder = LineDecoder()
        payload = encode_message(build_ping(1, 0.5))
        messages = decoder.feed(payload)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['type'], C.MSG_PING)

    def test_split_across_chunks(self):
        decoder = LineDecoder()
        payload = encode_message(build_hello('Bob', 'usa:T1'))
        mid = len(payload) // 2
        first = decoder.feed(payload[:mid])
        self.assertEqual(first, [])
        second = decoder.feed(payload[mid:])
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]['name'], 'Bob')

    def test_multiple_messages_and_blank_lines(self):
        decoder = LineDecoder()
        chunk = (
            encode_message(build_leave()) +
            b'\n' +
            encode_message(build_ping(2, 1.0)) +
            b'\n\n'
        )
        messages = decoder.feed(chunk)
        self.assertEqual(
            [m['type'] for m in messages],
            [C.MSG_LEAVE, C.MSG_PING])

    def test_skips_invalid_json(self):
        decoder = LineDecoder()
        chunk = b'not-json\n' + encode_message(build_leave())
        messages = decoder.feed(chunk)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['type'], C.MSG_LEAVE)

    def test_overflow_on_huge_buffer(self):
        decoder = LineDecoder(max_buffer_bytes=64)
        messages = decoder.feed(b'x' * 100)
        self.assertEqual(messages, [])
        self.assertTrue(decoder.overflow)

    def test_flush_leftover_half_line(self):
        decoder = LineDecoder()
        payload = encode_message(build_leave(), with_delimiter=False)
        self.assertEqual(decoder.feed(payload), [])
        messages = decoder.flush()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['type'], C.MSG_LEAVE)


if __name__ == '__main__':
    unittest.main()
