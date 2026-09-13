# -*- coding: utf-8 -*-
"""Intercept Offline single-player battle enter so LAN join can take over.

Patches ``gui.mods.offhangar2.fake_server`` after Offline hangar loads:
``CMD_ENQUEUE_IN_BATTLE_QUEUE`` must never call ``battle.enterRandom``.
"""
from __future__ import absolute_import, division, print_function

import sys

LOG_PREFIX = '[VVG join_gate] '

_installed = False
_handler = None  # callable(veh_inv_id, arena_type_id) -> None
_orig_enqueue = None
_orig_enter_random = None


def _log(message):
    try:
        sys.stdout.write(LOG_PREFIX + str(message) + '\n')
        sys.stdout.flush()
    except Exception:
        pass


def set_handler(handler):
    """Install callback invoked on intercepted Battle! clicks."""
    global _handler
    _handler = handler


def handler():
    return _handler


def _call_handler(veh_inv_id, arena_type_id):
    if _handler is None:
        _log('join requested vehInvID=%s arenaTypeID=%s (no handler)' % (
            veh_inv_id, arena_type_id))
        return
    try:
        _handler(veh_inv_id, arena_type_id)
    except Exception as exc:
        _log('handler failed: %s' % exc)


def _intercepted_enqueue(requestID, args):
    """Replacement for Offline _cmdEnqueueInBattleQueue."""
    arr = args[0] if args else []
    veh_inv_id = arr[1] if len(arr) > 1 else None
    arena_type_id = arr[3] if len(arr) > 3 else 0
    _log('intercepted CMD_ENQUEUE vehInvID=%s arenaTypeID=%s' % (
        veh_inv_id, arena_type_id))
    try:
        _respond_success(requestID)
    except Exception as exc:
        _log('respond failed: %s' % exc)
    _call_handler(veh_inv_id, arena_type_id)


def _respond_success(requestID):
    """Ack enqueue so the Flash lobby does not stick on a spinner."""
    try:
        from gui.mods.offhangar2 import fake_server
        respond = getattr(fake_server, '_respond', None)
        if callable(respond):
            try:
                from AccountCommands import AccountCommands
                success = getattr(AccountCommands, 'RES_SUCCESS', 0)
            except Exception:
                success = 0
            respond(requestID, success, '')
            return
    except Exception:
        pass


def _intercepted_enter_random(vehInvID=None, arenaTypeID=0, *args, **kwargs):
    """Fallback if something still calls battle.enterRandom."""
    _log('intercepted battle.enterRandom vehInvID=%s arenaTypeID=%s' % (
        vehInvID, arenaTypeID))
    _call_handler(vehInvID, arenaTypeID)
    return False


def install():
    """Patch Offline modules. Idempotent. Returns True if patched."""
    global _installed, _orig_enqueue, _orig_enter_random
    if _installed:
        return True

    try:
        from gui.mods.offhangar2 import fake_server
    except Exception as exc:
        _log('fake_server unavailable: %s' % exc)
        return False

    patched = False

    orig = getattr(fake_server, '_cmdEnqueueInBattleQueue', None)
    if callable(orig):
        _orig_enqueue = orig
        fake_server._cmdEnqueueInBattleQueue = _intercepted_enqueue
        try:
            import AccountCommands
            cmd = getattr(AccountCommands, 'CMD_ENQUEUE_IN_BATTLE_QUEUE', None)
            commands = getattr(fake_server, '_COMMANDS', None)
            if cmd is not None and isinstance(commands, dict):
                commands[cmd] = _intercepted_enqueue
        except Exception as exc:
            _log('rebind _COMMANDS failed: %s' % exc)
        patched = True
        _log('patched fake_server CMD_ENQUEUE_IN_BATTLE_QUEUE')

    try:
        from gui.mods.offhangar2 import battle
        orig_er = getattr(battle, 'enterRandom', None)
        if callable(orig_er):
            _orig_enter_random = orig_er
            battle.enterRandom = _intercepted_enter_random
            patched = True
            _log('patched battle.enterRandom fallback')
    except Exception as exc:
        _log('battle patch skipped: %s' % exc)

    if patched:
        _installed = True
    return patched


def uninstall():
    """Best-effort restore of original Offline handlers."""
    global _installed
    if not _installed:
        return
    try:
        from gui.mods.offhangar2 import fake_server
        if _orig_enqueue is not None:
            fake_server._cmdEnqueueInBattleQueue = _orig_enqueue
            try:
                import AccountCommands
                cmd = getattr(AccountCommands, 'CMD_ENQUEUE_IN_BATTLE_QUEUE', None)
                commands = getattr(fake_server, '_COMMANDS', None)
                if cmd is not None and isinstance(commands, dict):
                    commands[cmd] = _orig_enqueue
            except Exception:
                pass
    except Exception:
        pass
    try:
        from gui.mods.offhangar2 import battle
        if _orig_enter_random is not None:
            battle.enterRandom = _orig_enter_random
    except Exception:
        pass
    _installed = False
    _log('uninstalled')


def is_installed():
    return bool(_installed)


__all__ = [
    'install',
    'uninstall',
    'is_installed',
    'set_handler',
    'handler',
]
