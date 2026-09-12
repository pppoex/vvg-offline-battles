# -*- coding: utf-8 -*-
"""BigWorld mod entry for the VVG multi-client instance guard (2.3.1.2).

Installed to:
    res_mods/2.3.1.2/scripts/client/gui/mods/mod_vvg_instance_guard.py

The engine imports this module after Python init and calls init().
At that point WOT_STARTUP_MUTEX (and any WGC AppMutex) held by this process
is closed so a subsequent offline client can start without the
"already running" dialog.
"""
from __future__ import print_function

from gui.mods.vvg_instance_guard import bootstrap


def init():
    bootstrap.init()


def fini():
    bootstrap.fini()
