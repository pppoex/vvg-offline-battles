# -*- coding: utf-8 -*-
"""Scan 2.3.1.2 PE binaries for instance/mutex-related strings.

Python 2.7 compatible. Read-only against the game install.
"""
from __future__ import print_function

import os
import re
import struct
import sys

NEEDLES = [
    'wot_client',
    'mutex',
    'Mutex',
    'AppMutex',
    'instance',
    'CreateMutex',
    'already',
    'single',
    'running',
    'wgc',
    'WGC',
    'one instance',
    'already running',
]

GAME_WIN64 = r'D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\win64'
TARGETS = [
    os.path.join(GAME_WIN64, 'WorldOfTanks.exe'),
    os.path.join(GAME_WIN64, 'wgc_api.dll'),
    os.path.join(GAME_WIN64, 'wgcs_api.dll'),
    os.path.join(GAME_WIN64, 'wgc360_api.dll'),
]


def rva_to_off(data, rva):
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    opt_off = e_lfanew + 24
    num_sections = struct.unpack_from('<H', data, e_lfanew + 6)[0]
    size_opt = struct.unpack_from('<H', data, e_lfanew + 20)[0]
    sec_off = e_lfanew + 24 + size_opt
    for i in range(num_sections):
        off = sec_off + i * 40
        vsz, va, rsz, roff = struct.unpack_from('<IIII', data, off + 8)
        if va <= rva < va + max(vsz, rsz):
            return roff + (rva - va)
    return None


def pe_identity(path):
    with open(path, 'rb') as f:
        data = f.read(4096)
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    machine = struct.unpack_from('<H', data, e_lfanew + 4)[0]
    time_date_stamp = struct.unpack_from('<I', data, e_lfanew + 8)[0]
    opt_off = e_lfanew + 24
    magic = struct.unpack_from('<H', data, opt_off)[0]
    if magic == 0x20B:
        image_base = struct.unpack_from('<Q', data, opt_off + 24)[0]
        size_of_image = struct.unpack_from('<I', data, opt_off + 56)[0]
        subsystem = struct.unpack_from('<H', data, opt_off + 68)[0]
        return {
            'machine': machine,
            'timestamp': time_date_stamp,
            'image_base': image_base,
            'size_of_image': size_of_image,
            'subsystem': subsystem,
            'pe': 'PE32+',
        }
    image_base = struct.unpack_from('<I', data, opt_off + 28)[0]
    size_of_image = struct.unpack_from('<I', data, opt_off + 56)[0]
    return {
        'machine': machine,
        'timestamp': time_date_stamp,
        'image_base': image_base,
        'size_of_image': size_of_image,
        'pe': 'PE32',
    }


def parse_exports(path):
    with open(path, 'rb') as f:
        data = f.read()
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    opt_off = e_lfanew + 24
    magic = struct.unpack_from('<H', data, opt_off)[0]
    if magic != 0x20B:
        return []
    export_rva = struct.unpack_from('<I', data, opt_off + 112)[0]
    if export_rva == 0:
        return []
    exp_off = rva_to_off(data, export_rva)
    if exp_off is None:
        return []
    num_names = struct.unpack_from('<I', data, exp_off + 24)[0]
    names_rva = struct.unpack_from('<I', data, exp_off + 32)[0]
    ords_rva = struct.unpack_from('<I', data, exp_off + 36)[0]
    funcs_rva = struct.unpack_from('<I', data, exp_off + 28)[0]
    names_off = rva_to_off(data, names_rva)
    ords_off = rva_to_off(data, ords_rva)
    funcs_off = rva_to_off(data, funcs_rva)
    exports = []
    for i in range(num_names):
        name_rva = struct.unpack_from('<I', data, names_off + i * 4)[0]
        name_off = rva_to_off(data, name_rva)
        if name_off is None:
            continue
        end = data.find(b'\x00', name_off)
        name = data[name_off:end].decode('ascii', 'ignore')
        ord_idx = struct.unpack_from('<H', data, ords_off + i * 2)[0]
        func_rva = struct.unpack_from('<I', data, funcs_off + ord_idx * 4)[0]
        exports.append((name, func_rva))
    return exports


def find_ascii_strings(data, minlen=4):
    for m in re.finditer(b'[\x20-\x7e]{%d,}' % minlen, data):
        yield m.start(), m.group().decode('ascii', 'ignore')


def find_utf16_strings(data, minlen=4):
    pattern = b'(?:[\x20-\x7e]\x00){%d,}' % minlen
    for m in re.finditer(pattern, data):
        yield m.start(), m.group().decode('utf-16le', 'ignore')


def sample_hits(items, limit=15):
    seen = set()
    out = []
    for off, s in items:
        key = s.strip()
        if key in seen:
            continue
        seen.add(key)
        out.append('0x%X: %s' % (off, s[:140].replace('\r', ' ').replace('\n', ' ')))
        if len(out) >= limit:
            break
    return out


def scan_file(path):
    print('===== %s =====' % path)
    ident = pe_identity(path)
    print('Machine=0x%04X Timestamp=0x%08X ImageBase=0x%016X SizeOfImage=0x%08X PE=%s' % (
        ident['machine'], ident['timestamp'], ident['image_base'],
        ident['size_of_image'], ident['pe']))
    exports = parse_exports(path)
    print('ExportCount=%d' % len(exports))
    if exports:
        for name, rva in exports[:40]:
            print('  export 0x%08X %s' % (rva, name))
        if len(exports) > 40:
            print('  ... (%d more)' % (len(exports) - 40))

    with open(path, 'rb') as f:
        data = f.read()

    print('-- ASCII string hits --')
    ascii_index = dict((n, []) for n in NEEDLES)
    for off, s in find_ascii_strings(data, 4):
        low = s.lower()
        for n in NEEDLES:
            if n.lower() in low:
                ascii_index[n].append((off, s))
    for n in NEEDLES:
        items = ascii_index[n]
        if not items:
            continue
        print('[%s] count=%d' % (n, len(items)))
        for line in sample_hits(items):
            print('  ', line)

    print('-- UTF-16 string hits --')
    utf_index = dict((n, []) for n in NEEDLES)
    for off, s in find_utf16_strings(data, 4):
        low = s.lower()
        for n in NEEDLES:
            if n.lower() in low:
                utf_index[n].append((off, s))
    for n in NEEDLES:
        items = utf_index[n]
        if not items:
            continue
        print('[%s] count=%d' % (n, len(items)))
        for line in sample_hits(items):
            print('  ', line)
    print('')


def main():
    for path in TARGETS:
        if not os.path.isfile(path):
            print('MISSING: %s' % path)
            continue
        scan_file(path)


if __name__ == '__main__':
    main()
