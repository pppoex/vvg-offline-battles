# -*- coding: utf-8 -*-
"""日志系统 — 从 Offline2.3.1.2 log.py 抽取并修复 Decompyle++ artifact。

写入本地日志文件；在游戏内若 debug_utils 可用则转发到引擎日志。
"""
from __future__ import absolute_import, division, print_function

import os
import sys
import time
import traceback

PREFIX = '[VVG]'
LOG_NAME = 'vvg_sdk.log'

_ERROR = None
try:
    from debug_utils import LOG_ERROR as _ERROR
except Exception:
    _ERROR = None

_file = None
_file_failed = False


def _stamp():
    try:
        now = time.time()
        millis = int((now % 1) * 1000)
        return '%s.%03d:' % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now)), millis)
    except Exception:
        return '?:'


def _candidate_paths():
    paths = []
    try:
        paths.append(os.path.join(os.getcwd(), LOG_NAME))
    except Exception:
        pass

    # 游戏内：优先写到 preferences 同目录（与 Offline 一致）
    try:
        import BigWorld  # noqa: F401
        try:
            from external_strings_utils import unicode_from_utf8
        except Exception:
            unicode_from_utf8 = None
        if unicode_from_utf8 is not None:
            prefs = unicode_from_utf8(BigWorld.wg_getPreferencesFilePath())[1]
            paths.append(os.path.join(os.path.dirname(prefs), LOG_NAME))
    except Exception:
        pass

    return paths


def open_file():
    """返回已打开的日志句柄；失败返回 None。幂等。"""
    global _file, _file_failed
    if _file is not None or _file_failed:
        return _file
    for path in _candidate_paths():
        try:
            handle = open(path, 'wb', 0)
        except Exception:
            continue
        header = '%s log start at %s\n' % (PREFIX, path)
        try:
            handle.write(header.encode('utf-8') if isinstance(header, type(u'')) else header)
        except Exception:
            try:
                handle.write(header)
            except Exception:
                pass
        _file = handle
        return _file
    _file_failed = True
    return None


def emit(line):
    """写入一行：文件 + 引擎日志（若有）+ stdout。"""
    text = '%s %s' % (PREFIX, line)
    handle = open_file()
    if handle is not None:
        try:
            stamped = '%s %s\n' % (_stamp(), text)
            try:
                handle.write(stamped.encode('utf-8'))
            except Exception:
                handle.write(stamped)
        except Exception:
            pass

    if _ERROR is not None:
        try:
            _ERROR(text)
            return None
        except Exception:
            pass

    try:
        print(text)
    except Exception:
        pass


def info(fmt, *args):
    try:
        emit(fmt % args if args else fmt)
    except Exception:
        emit(repr(fmt))


def err(fmt, *args):
    try:
        emit('ERROR: ' + (fmt % args if args else fmt))
    except Exception:
        emit('ERROR: ' + repr(fmt))


def exc(context=''):
    label = context if context else '?'
    emit('EXCEPTION in %s' % label)
    try:
        for line in traceback.format_exc().splitlines():
            emit('    ' + line)
    except Exception:
        pass


def guard(context):
    """装饰器：捕获异常并记入日志，失败返回 None。"""

    def _decorator(func):
        def _wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                exc(context)
                return None

        _wrapper.__name__ = getattr(func, '__name__', 'wrapped')
        _wrapper.__doc__ = getattr(func, '__doc__', None)
        return _wrapper

    return _decorator


def reset_for_tests():
    """仅用于单元测试：关闭并清空内部文件句柄状态。"""
    global _file, _file_failed
    if _file is not None:
        try:
            _file.close()
        except Exception:
            pass
    _file = None
    _file_failed = False
