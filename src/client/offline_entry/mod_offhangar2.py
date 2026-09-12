# -*- coding: utf-8 -*-
"""Fixed BigWorld mod entry for Offline hangar (decompyle artifact cleaned).

Source of truth for deploy: Offline2.3.1.2 is read-only; install_offhangar
overwrites this file into res_mods after copying the Offline package.

Original Decompyle++ produced::

    def init():
        offhangar2 = offhangar2   # UnboundLocalError

Real code must import the package first.
"""
from __future__ import print_function


def _patchWulfPresenters():
    try:
        VehicleInventoryPresenter = VehicleInventoryPresenter
        import gui.impl.lobby.hangar.presenters.vehicle_inventory_presenter
        orig_vip_finalize = VehicleInventoryPresenter._finalize

        def _safe_vip_finalize(self):
            try:
                if getattr(self, '_VehicleInventoryPresenter__telecomRentals', None) is None:
                    import BigWorld
                    player = BigWorld.player()
                    if player and hasattr(player, 'telecomRentals') and player.telecomRentals is not None:
                        setattr(self, '_VehicleInventoryPresenter__telecomRentals', player.telecomRentals)
                    else:
                        class _DummyTR(object):
                            from Event import Event
                            onPendingRentChanged = Event()

                        setattr(self, '_VehicleInventoryPresenter__telecomRentals', _DummyTR())
            except Exception:
                pass

            try:
                return orig_vip_finalize(self)
            except Exception:
                pass

        VehicleInventoryPresenter._finalize = _safe_vip_finalize
    except Exception:
        pass


def init():
    _patchWulfPresenters()
    from gui.mods import offhangar2
    offhangar2.install()

    try:
        from gui.mods.offhangar2 import friends
        friends.init()
    except Exception:
        pass


def fini():
    from gui.mods import offhangar2
    offhangar2.uninstall()


def _enableArmorFlashlightEverywhere():
    """Best-effort enable of WG armor flashlight in offline (optional)."""
    try:
        from gui.armor_flashlight import config as af_config
        if hasattr(af_config, 'isFeatureEnabled'):
            af_config.isFeatureEnabled = lambda *a, **k: True
    except Exception:
        pass
    try:
        from account_helpers.settings_core import options as core_options
        if hasattr(core_options, 'isArmorFlashlightEnabled'):
            core_options.isArmorFlashlightEnabled = lambda *a, **k: True
    except Exception:
        pass


def _enableArmorInspectorEverywhere():
    try:
        from gui.impl.lobby.hangar.presenters.vehicle_menu_entries import (
            armor_inspector_entry_sub_presenter as aiesp)
        ArmorInspectorEntrySubPresenter = aiesp.ArmorInspectorEntrySubPresenter
        try:
            from gui.impl.gen.view_models.views.lobby.hangar.vehicle_menu_model import (
                VehicleMenuModel)

            def _safe_getState(self):
                try:
                    from CurrentVehicle import g_currentVehicle
                    vehicle = g_currentVehicle.item
                    if vehicle is None or g_currentVehicle.isInBattle():
                        return VehicleMenuModel.DISABLED
                    return None.ENABLED
                except Exception:
                    return VehicleMenuModel.DISABLED
        except Exception:
            def _safe_getState(self):
                return None

        ArmorInspectorEntrySubPresenter._getState = _safe_getState
    except Exception:
        pass


_prevInit = init


def _initWithArmorTools():
    """init() plus optional WG feature unlocks (must run before install)."""
    _enableArmorFlashlightEverywhere()
    _enableArmorInspectorEverywhere()
    return _prevInit()


init = _initWithArmorTools
