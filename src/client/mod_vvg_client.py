# -*- coding: utf-8 -*-
"""BigWorld mod entry for the VVG thin client (2.3.1.2).

Installed to:
    res_mods/2.3.1.2/scripts/client/gui/mods/mod_vvg_client.py

The engine imports this module after Python init and calls init().
Any exception is swallowed: a broken thin client must never kill game.init.
"""
from __future__ import print_function


def _safe_log(message):
    try:
        sys_stdout = __import__('sys').stdout
        sys_stdout.write('[VVG thin client] %s\n' % message)
        sys_stdout.flush()
    except Exception:
        pass


def init():
    try:
        from gui.mods.vvg_client import bootstrap
    except Exception as import_error:
        _safe_log('import bootstrap failed: %s' % import_error)
        return
    try:
        bootstrap.init()
    except Exception as init_error:
        _safe_log('bootstrap.init failed: %s' % init_error)


def fini():
    try:
        from gui.mods.vvg_client import bootstrap
    except Exception:
        return
    try:
        bootstrap.fini()
    except Exception as fini_error:
        _safe_log('bootstrap.fini failed: %s' % fini_error)
