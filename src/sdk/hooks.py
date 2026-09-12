# -*- coding: utf-8 -*-
"""Hook 系统 — 从 Offline2.3.1.2 hooks.py 抽取并修复 Decompyle++ artifact。

提供：
- resolveName: 修正私有名 name mangling
- override: 装饰器，把 replacement(original, *args, **kwargs) 挂到 holder 上
- setAttr: 安全 setattr
"""
from __future__ import absolute_import, division, print_function

import inspect

from . import log


def resolve_name(holder, name):
    """解析属性名；类上的 `__foo` 需按 Python mangling 换算。"""
    if (inspect.isclass(holder)
            and name.startswith('__')
            and not name.endswith('__')
            and name not in dir(holder)):
        mangled = '_%s%s' % (holder.__name__.lstrip('_'), name)
        if hasattr(holder, mangled):
            return mangled
    return name


# 兼容 Offline 命名
resolveName = resolve_name


def override(holder, name):
    """装饰器：替换 holder.name，原函数作为第一参数传入 replacement。

    重复 patch 同一 (module, name) 时返回已包装函数，保证幂等。
    """

    def _decorator(replacement):
        real_name = resolve_name(holder, name)

        try:
            original = getattr(holder, real_name)
        except AttributeError:
            log.err('override: %r has no attribute %r', holder, real_name)
            return replacement

        tag = (getattr(replacement, '__module__', None),
               getattr(replacement, '__name__', real_name))
        if getattr(original, '_vvg_tag', None) == tag:
            return original

        def _wrapper(*args, **kwargs):
            return replacement(original, *args, **kwargs)

        _wrapper.__name__ = getattr(replacement, '__name__', real_name)
        _wrapper.__doc__ = getattr(replacement, '__doc__', None)
        _wrapper._vvg_original = original
        _wrapper._vvg_tag = tag

        try:
            setattr(holder, real_name, _wrapper)
        except Exception:
            log.exc('override(%r, %r)' % (holder, real_name))
            return replacement

        log.info('patched %s.%s', getattr(holder, '__name__', holder), real_name)
        return _wrapper

    return _decorator


def set_attr(holder, name, value):
    """安全 setattr，返回是否成功。"""
    real_name = resolve_name(holder, name)
    try:
        setattr(holder, real_name, value)
        log.info('set %s.%s', getattr(holder, '__name__', holder), real_name)
        return True
    except Exception:
        log.exc('setAttr(%r, %r)' % (holder, real_name))
        return False


# 兼容 Offline 命名
setAttr = set_attr
