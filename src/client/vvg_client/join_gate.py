# -*- coding: utf-8 -*-
"""Intercept Offline/stock battle enter so LAN join can take over.

Earliest hook: ``LobbyHeader.fightClick`` (same idea as 0.9.22 JoinButtonUI),
so the retail "Joining..." waiting screen never opens.

Fallback hooks: Offline ``fake_server`` CMD_ENQUEUE and ``battle.enterRandom``.
"""
from __future__ import absolute_import, division, print_function

import sys

LOG_PREFIX = '[VVG join_gate] '

_installed = False
_handler = None
_orig_enqueue = None
_orig_enter_random = None
_fight_button = None  # dict describing LobbyHeader patch state


def _log(message):
    try:
        sys.stdout.write(LOG_PREFIX + str(message) + '\n')
        sys.stdout.flush()
    except Exception:
        pass


def set_handler(handler):
    global _handler
    _handler = handler


def handler():
    return _handler


def _call_handler(veh_inv_id, arena_type_id):
    if _handler is None:
        _log('join requested vehInvID=%s arenaTypeID=%s (no handler)' % (
            veh_inv_id, arena_type_id))
        return False
    try:
        _handler(veh_inv_id, arena_type_id)
        return True
    except Exception as exc:
        _log('handler failed: %s' % exc)
        return False


def _intercepted_enqueue(requestID, args):
    arr = args[0] if args else []
    veh_inv_id = arr[1] if len(arr) > 1 else None
    arena_type_id = arr[3] if len(arr) > 3 else 0
    _log('intercepted CMD_ENQUEUE vehInvID=%s arenaTypeID=%s' % (
        veh_inv_id, arena_type_id))
    hide_waiting_overlay()
    try:
        _respond_success(requestID)
    except Exception as exc:
        _log('respond failed: %s' % exc)
    _call_handler(veh_inv_id, arena_type_id)


def _respond_success(requestID):
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
    _log('intercepted battle.enterRandom vehInvID=%s arenaTypeID=%s' % (
        vehInvID, arenaTypeID))
    hide_waiting_overlay()
    _call_handler(vehInvID, arenaTypeID)
    return False


def _wrapped_fight_click(header, map_id=None, action_name=None):
    """Earliest Battle! click — never fall through to stock joining screen."""
    _log('fightClick map_id=%s action=%s' % (map_id, action_name))
    hide_waiting_overlay()
    veh = None
    arena = 0
    try:
        if header is not None:
            veh = getattr(header, 'selectedVehicleInvID', None)
    except Exception:
        pass
    _call_handler(veh, arena)
    return None


def _patch_fight_button():
    """Patch LobbyHeader.fightClick. Returns True if newly patched."""
    global _fight_button
    if _fight_button is not None:
        return False
    header_type = _resolve_lobby_header_type()
    if header_type is None:
        _log('LobbyHeader unavailable (all import paths failed)')
        return False

    had_own = 'fightClick' in header_type.__dict__
    original = header_type.__dict__.get(
        'fightClick', getattr(header_type, 'fightClick', None))
    if not callable(original):
        _log('LobbyHeader.fightClick missing')
        return False

    wrapper = _wrapped_fight_click
    try:
        header_type.fightClick = wrapper
    except Exception as exc:
        _log('assign fightClick failed: %s' % exc)
        return False
    _fight_button = {
        'type': header_type,
        'original': original,
        'wrapper': wrapper,
        'had_own': had_own,
    }
    _log('patched LobbyHeader.fightClick on %s' % getattr(
        header_type, '__name__', header_type))
    return True


def _resolve_lobby_header_type():
    """Find LobbyHeader class on 2.3.1.2 without assuming one import path."""
    candidates = (
        'gui.Scaleform.daapi.view.lobby.header.LobbyHeader',
        'gui.Scaleform.daapi.view.lobby.header.lobby_header',
        'gui.Scaleform.daapi.view.meta.LobbyHeaderMeta',
    )
    try:
        import importlib
    except Exception:
        importlib = None

    if importlib is not None:
        for path in candidates:
            try:
                module = importlib.import_module(path)
            except Exception as exc:
                _log('import %s failed: %s' % (path, exc))
                continue
            for attr in ('LobbyHeader', 'LobbyHeaderMeta'):
                found = getattr(module, attr, None)
                if isinstance(found, type):
                    return found

    # After lobby load, the class may already be in sys.modules.
    try:
        import sys
        for name, module in list(sys.modules.items()):
            if module is None:
                continue
            if 'LobbyHeader' not in name and 'lobby.header' not in name:
                continue
            for attr in ('LobbyHeader', 'LobbyHeaderMeta'):
                found = getattr(module, attr, None)
                if isinstance(found, type) and callable(
                        getattr(found, 'fightClick', None)):
                    return found
    except Exception:
        pass
    return None


def hide_waiting_overlay():
    """Dismiss stock joining/waiting UI (gui.Scaleform.Waiting)."""
    try:
        from gui.Scaleform import Waiting
        hide = getattr(Waiting, 'hide', None)
        if callable(hide):
            try:
                hide()
            except TypeError:
                hide('join')
            return True
    except Exception:
        pass
    return False


def install():
    """Install all available hooks. Idempotent; safe to retry."""
    global _installed, _orig_enqueue, _orig_enter_random
    patched_any = False

    # --- Offline CMD_ENQUEUE / enterRandom ---
    try:
        from gui.mods.offhangar2 import fake_server
    except Exception as exc:
        _log('fake_server unavailable: %s' % exc)
    else:
        orig = getattr(fake_server, '_cmdEnqueueInBattleQueue', None)
        if callable(orig) and _orig_enqueue is None:
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
            patched_any = True
            _log('patched fake_server CMD_ENQUEUE')

    try:
        from gui.mods.offhangar2 import battle
        orig_er = getattr(battle, 'enterRandom', None)
        if callable(orig_er) and _orig_enter_random is None:
            _orig_enter_random = orig_er
            battle.enterRandom = _intercepted_enter_random
            patched_any = True
            _log('patched battle.enterRandom')
    except Exception as exc:
        _log('battle patch skipped: %s' % exc)

    # --- Earliest: LobbyHeader.fightClick ---
    if _patch_fight_button():
        patched_any = True

    if patched_any:
        _installed = True
    return patched_any or _installed


def uninstall():
    global _installed, _fight_button
    if _fight_button is not None:
        state = _fight_button
        _fight_button = None
        try:
            header_type = state['type']
            current = header_type.__dict__.get(
                'fightClick', getattr(header_type, 'fightClick', None))
            if current is state['wrapper']:
                if state['had_own']:
                    header_type.fightClick = state['original']
                else:
                    try:
                        delattr(header_type, 'fightClick')
                    except Exception:
                        header_type.fightClick = state['original']
        except Exception:
            pass
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


def fight_button_installed():
    return _fight_button is not None


__all__ = [
    'install',
    'uninstall',
    'is_installed',
    'fight_button_installed',
    'hide_waiting_overlay',
    'set_handler',
    'handler',
]
