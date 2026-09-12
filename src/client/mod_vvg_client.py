# -*- coding: utf-8 -*-
"""BigWorld mod entry for the VVG thin client (2.3.1.2).

Installed to:
    res_mods/2.3.1.2/scripts/client/gui/mods/mod_vvg_client.py

The engine imports this module after Python init and calls init().
Identity / server address come from environment (VVG_*) or sdk.config defaults.
"""
from __future__ import print_function

from gui.mods.vvg_client import bootstrap


def init():
    bootstrap.init()


def fini():
    bootstrap.fini()
