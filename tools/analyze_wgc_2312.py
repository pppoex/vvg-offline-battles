# -*- coding: utf-8 -*-
"""Deeper WGC / Python API analysis for WoT 2.3.1.2 x64."""
from __future__ import print_function

import os
import struct
import re

GAME = r'D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2\win64'
EXE = os.path.join(GAME, 'WorldOfTanks.exe')
WGC = os.path.join(GAME, 'wgc_api.dll')


def rva_to_off(data, rva):
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    opt_off = e_lfanew + 24
    num_sections = struct.unpack_from('<H', data, e_lfanew + 6)[0]
    size_opt = struct.unpack_from('<H', data, e_lfanew + 20)[0]
    sec_off = e_lfanew + 24 + size_opt
    for i in range(num_sections):
        off = sec_off + i * 40
        name = data[off:off + 8].split(b'\x00')[0]
        vsz, va, rsz, roff = struct.unpack_from('<IIII', data, off + 8)
        if va <= rva < va + max(vsz, rsz):
            return roff + (rva - va), name, va, vsz
    return None, None, None, None


def load(path):
    with open(path, 'rb') as f:
        return f.read()


def file_off_to_rva(data, off):
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    opt_off = e_lfanew + 24
    num_sections = struct.unpack_from('<H', data, e_lfanew + 6)[0]
    size_opt = struct.unpack_from('<H', data, e_lfanew + 20)[0]
    sec_off = e_lfanew + 24 + size_opt
    for i in range(num_sections):
        soff = sec_off + i * 40
        vsz, va, rsz, roff = struct.unpack_from('<IIII', data, soff + 8)
        if roff <= off < roff + rsz:
            return va + (off - roff)
    return None


def parse_exports_full(path):
    data = load(path)
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    opt_off = e_lfanew + 24
    export_rva = struct.unpack_from('<I', data, opt_off + 112)[0]
    exp_off = rva_to_off(data, export_rva)[0]
    num_names = struct.unpack_from('<I', data, exp_off + 24)[0]
    names_rva = struct.unpack_from('<I', data, exp_off + 32)[0]
    ords_rva = struct.unpack_from('<I', data, exp_off + 36)[0]
    funcs_rva = struct.unpack_from('<I', data, exp_off + 28)[0]
    names_off = rva_to_off(data, names_rva)[0]
    ords_off = rva_to_off(data, ords_rva)[0]
    funcs_off = rva_to_off(data, funcs_rva)[0]
    exports = []
    for i in range(num_names):
        name_rva = struct.unpack_from('<I', data, names_off + i * 4)[0]
        name_off = rva_to_off(data, name_rva)[0]
        end = data.find(b'\x00', name_off)
        name = data[name_off:end].decode('ascii', 'ignore')
        ord_idx = struct.unpack_from('<H', data, ords_off + i * 2)[0]
        func_rva = struct.unpack_from('<I', data, funcs_off + ord_idx * 4)[0]
        exports.append((name, func_rva))
    return exports


def parse_imports(path):
    data = load(path)
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    opt_off = e_lfanew + 24
    import_rva = struct.unpack_from('<I', data, opt_off + 120)[0]
    if import_rva == 0:
        return []
    imp_off = rva_to_off(data, import_rva)[0]
    results = []
    idx = 0
    while True:
        entry_off = imp_off + idx * 20
        ilt_rva = struct.unpack_from('<I', data, entry_off)[0]
        name_rva = struct.unpack_from('<I', data, entry_off + 12)[0]
        if ilt_rva == 0 and name_rva == 0:
            break
        name_off = rva_to_off(data, name_rva)[0]
        dll = data[name_off:data.find(b'\x00', name_off)].decode('ascii', 'ignore')
        funcs = []
        # walk IAT/ILT
        thunk_rva = ilt_rva or struct.unpack_from('<I', data, entry_off + 16)[0]
        thunk_off = rva_to_off(data, thunk_rva)[0]
        j = 0
        while True:
            thunk = struct.unpack_from('<Q', data, thunk_off + j * 8)[0]
            if thunk == 0:
                break
            if thunk & (1 << 63):
                funcs.append('#%d' % (thunk & 0xFFFF))
            else:
                hint_off = rva_to_off(data, thunk)[0]
                fname = data[hint_off + 2:data.find(b'\x00', hint_off + 2)].decode('ascii', 'ignore')
                funcs.append(fname)
            j += 1
            if j > 400:
                break
        results.append((dll, funcs))
        idx += 1
        if idx > 200:
            break
    return results


def find_all(data, pattern):
    hits = []
    start = 0
    while True:
        i = data.find(pattern, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    return hits


def dump_utf16_near(data, off, before=0, after=200):
    chunk = data[max(0, off - before):off + after]
    # try decode surrounding as utf16
    return chunk.decode('utf-16le', 'ignore')


def main():
    print('=== WGCApi* / Python API exports in WorldOfTanks.exe ===')
    exe_exports = parse_exports_full(EXE)
    for name, rva in sorted(exe_exports, key=lambda x: x[0]):
        lname = name.lower()
        if ('wgcapi' in lname or 'pyinit' in lname or 'py_init' in lname
                or name.startswith('Py') or 'PyInit' in name
                or 'AppMutex' in name or 'mutex' in lname):
            print('  0x%08X %s' % (rva, name))

    print('\n=== Interesting non-mangled exports (short) ===')
    for name, rva in sorted(exe_exports, key=lambda x: x[0]):
        if not name.startswith('?') and not name.startswith('_'):
            print('  0x%08X %s' % (rva, name))

    print('\n=== wgc_api.dll WGCApi exports ===')
    wgc_exports = parse_exports_full(WGC)
    for name, rva in sorted(wgc_exports, key=lambda x: x[0]):
        if 'WGCApi' in name and not name.startswith('?$'):
            # skip cereal StaticObject noise somewhat
            if name.startswith('?'):
                if 'WGCApi' in name and ('binding_' in name or 'create@' in name.lower()):
                    pass
                if not (name.startswith('WGCApi') or 'binding_WGCApi' in name):
                    continue
            print('  0x%08X %s' % (rva, name))

    print('\n=== Direct C exports wgc_api (no leading ?) ===')
    for name, rva in sorted(wgc_exports, key=lambda x: x[0]):
        if not name.startswith('?') and not name.startswith('_'):
            print('  0x%08X %s' % (rva, name))

    print('\n=== wgc_api imports of mutex APIs ===')
    for dll, funcs in parse_imports(WGC):
        interesting = [f for f in funcs if 'Mutex' in f or 'WaitFor' in f or 'CloseHandle' in f]
        if interesting:
            print(dll, interesting)

    print('\n=== exe imports of mutex APIs ===')
    for dll, funcs in parse_imports(EXE):
        interesting = [f for f in funcs if 'Mutex' in f or 'wgc' in f.lower()]
        if interesting:
            print(dll, interesting)

    # Find all WGC-related imports in exe
    print('\n=== exe imports from wgc*.dll ===')
    for dll, funcs in parse_imports(EXE):
        if 'wgc' in dll.lower():
            print(dll, funcs)

    data = load(EXE)
    print('\n=== UTF-16 context around EWOT_STARTUP_MUTEX ===')
    for hit in find_all(data, 'EWOT_STARTUP_MUTEX'.encode('utf-16le')):
        print('  file_off=0x%X rva=0x%X' % (hit, file_off_to_rva(data, hit) or 0))
        # dump nearby utf16 strings
        window = data[hit - 128:hit + 256]
        # extract printable utf16 runs
        i = 0
        while i + 2 < len(window):
            j = i
            chars = []
            while j + 1 < len(window):
                lo, hi = window[j], window[j + 1]
                if hi == 0 and 32 <= lo < 127:
                    chars.append(chr(lo))
                    j += 2
                else:
                    break
            if len(chars) >= 4:
                print('    +0x%X: %s' % (i - 128, ''.join(chars)))
                i = j
            else:
                i += 1

    print('\n=== UTF-16 context around wgc_game_mtx_ in wgc_api ===')
    wdata = load(WGC)
    for hit in find_all(wdata, 'wgc_game_mtx_'.encode('utf-16le')):
        print('  file_off=0x%X rva=0x%X' % (hit, file_off_to_rva(wdata, hit) or 0))
        window = wdata[hit - 160:hit + 320]
        i = 0
        while i + 2 < len(window):
            j = i
            chars = []
            while j + 1 < len(window):
                lo, hi = window[j], window[j + 1]
                if hi == 0 and 32 <= lo < 127:
                    chars.append(chr(lo))
                    j += 2
                else:
                    break
            if len(chars) >= 4:
                print('    +0x%X: %s' % (i - 160, ''.join(chars)))
                i = j
            else:
                i += 1

    print('\n=== UTF-16 context around wgc_running_games_mtx ===')
    for hit in find_all(wdata, 'wgc_running_games_mtx'.encode('utf-16le')):
        print('  file_off=0x%X rva=0x%X' % (hit, file_off_to_rva(wdata, hit) or 0))
        window = wdata[hit - 80:hit + 200]
        i = 0
        while i + 2 < len(window):
            j = i
            chars = []
            while j + 1 < len(window):
                lo, hi = window[j], window[j + 1]
                if hi == 0 and 32 <= lo < 127:
                    chars.append(chr(lo))
                    j += 2
                else:
                    break
            if len(chars) >= 4:
                print('    +0x%X: %s' % (i - 80, ''.join(chars)))
                i = j
            else:
                i += 1

    # Search for WGCApi* import thunks in exe
    print('\n=== Search WGCApi strings near imports in exe ===')
    for s in ['WGCApiCreateInstance', 'WGCApiDestroyInstance', 'WGCApiFreeInstance',
              'WGCApiGetResultDescription', 'WGCApiIsAnotherGameRunning',
              'WGCApiHighlightAnotherInstance', 'WGCApiCreateGlobalInstance',
              'WGCApiFreeGlobalInstance']:
        b = s.encode('ascii')
        for hit in find_all(data, b):
            rva = file_off_to_rva(data, hit)
            print('  %s @ file=0x%X rva=0x%X' % (s, hit, rva or 0))


if __name__ == '__main__':
    main()
