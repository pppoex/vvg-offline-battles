# -*- coding: utf-8 -*-
"""Locate mutex-name construction and WGC controller symbols."""
from __future__ import print_function

import os
import struct
import re

GAME = r'D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\win64'
EXE = os.path.join(GAME, 'WorldOfTanks.exe')
WGC = os.path.join(GAME, 'wgc_api.dll')


def load(p):
    with open(p, 'rb') as f:
        return f.read()


def file_to_rva(data, off):
    e = struct.unpack_from('<I', data, 0x3C)[0]
    opt = e + 24
    ns = struct.unpack_from('<H', data, e + 6)[0]
    so = struct.unpack_from('<H', data, e + 20)[0]
    sec = e + 24 + so
    for i in range(ns):
        o = sec + i * 40
        vsz, va, rsz, roff = struct.unpack_from('<IIII', data, o + 8)
        if roff <= off < roff + max(rsz, 1):
            return va + (off - roff)
    return None


def extract_utf16_strings(data, minlen=4):
    out = []
    for m in re.finditer(b'(?:[\x20-\x7e]\x00){%d,}' % minlen, data):
        s = m.group().decode('utf-16le', 'ignore')
        out.append((m.start(), s))
    return out


def extract_ascii_strings(data, minlen=4):
    out = []
    for m in re.finditer(b'[\x20-\x7e]{%d,}' % minlen, data):
        out.append((m.start(), m.group().decode('ascii', 'ignore')))
    return out


def main():
    print('=== EXE UTF-16 strings containing mutex/wgc/startup/client ===')
    data = load(EXE)
    for off, s in extract_utf16_strings(data, 4):
        low = s.lower()
        if any(k in low for k in ('mutex', 'wgc_', 'startup', 'already run',
                                   'single instance', 'wot_client', 'ewot',
                                   'app_mutex', 'appmutex')):
            print('  0x%X rva=0x%X %s' % (off, file_to_rva(data, off) or 0, s[:160]))

    print('\n=== EXE ASCII strings containing WGCController / mutex / prepare ===')
    for off, s in extract_ascii_strings(data, 5):
        low = s.lower()
        if any(k in low for k in ('wgcontroller', 'wgccontroller', 'wgc api',
                                   'app_mutex', 'startup_mutex', 'client mutex',
                                   'wgcore', 'islaunchedfromwgc')):
            print('  0x%X rva=0x%X %s' % (off, file_to_rva(data, off) or 0, s[:160]))

    print('\n=== WGC UTF-16 mutex-related with context dump ===')
    wdata = load(WGC)
    keywords = ('wgc_game_mtx', 'wgc_running', 'already running', 'AppMutex',
                'Failed to create app mutex', 'game_mtx')
    for off, s in extract_utf16_strings(wdata, 4):
        if any(k.lower() in s.lower() for k in keywords):
            print('  0x%X rva=0x%X %s' % (off, file_to_rva(wdata, off) or 0, s[:180]))

    # Search for wide format strings that append suffixes
    print('\n=== WGC wide strings with %s / %lu near mutex ===')
    for off, s in extract_utf16_strings(wdata, 4):
        if ('mtx' in s.lower() or 'mutex' in s.lower() or 'already' in s.lower()) or \
           (('%' in s) and ('wgc' in s.lower() or 'game' in s.lower() or 'Local' in s or 'Global' in s)):
            print('  0x%X rva=0x%X %s' % (off, file_to_rva(wdata, off) or 0, s[:180]))

    # Look at bytes immediately after wgc_game_mtx_ for UTF-16 continuation (suffix)
    print('\n=== Bytes after wgc_game_mtx_ (possible suffix construction) ===')
    hit = wdata.find('wgc_game_mtx_'.encode('utf-16le'))
    if hit >= 0:
        # dump 64 bytes as words
        chunk = wdata[hit:hit + 64]
        words = []
        for i in range(0, len(chunk) - 1, 2):
            w = struct.unpack_from('<H', chunk, i)[0]
            words.append('U+%04X' % w)
        print(' ', ' '.join(words))
        # also before
        pre = wdata[hit - 32:hit]
        print(' before:', repr(pre))

    # Search EXE for CreateMutexW related string xrefs by finding UTF-16 EWOT and nearby
    print('\n=== Full UTF-16 neighborhood of EWOT_STARTUP_MUTEX ===')
    hit = data.find('EWOT_STARTUP_MUTEX'.encode('utf-16le'))
    if hit >= 0:
        window = data[hit - 200:hit + 400]
        # print all utf16 runs
        for m in re.finditer(b'(?:[\x20-\x7e]\x00){3,}', window):
            print('  off%+d: %s' % (m.start() - 200, m.group().decode('utf-16le', 'ignore')))
        print(' hex dump before:', repr(data[hit - 32:hit + 64]))

    # Check python.log for WGC related
    print('\n=== python.log WGC / mutex / already ===')
    log_path = r'D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\python.log'
    if os.path.isfile(log_path):
        with open(log_path, 'rb') as f:
            for line in f:
                try:
                    text = line.decode('utf-8', 'ignore')
                except Exception:
                    continue
                low = text.lower()
                if any(k in low for k in ('wgc', 'mutex', 'already run', 'instance',
                                          'app_mutex', 'multi')):
                    print(' ', text.rstrip()[:200])


if __name__ == '__main__':
    main()
