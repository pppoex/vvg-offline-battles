# -*- coding: utf-8 -*-
"""Intercept Offline/stock battle enter so LAN join can take over.

Earliest hook: ``LobbyHeader.fightClick`` (same idea as 0.9.22 JoinButtonUI),
so the retail "Joining..." waiting screen never opens.

Fallback hooks: Offline ``fake_server`` CMD_ENQUEUE and ``battle.enterRandom``.
"""
from __future__ import absolute_import, division, print_function

import sys
import time

LOG_PREFIX = '[VVG join_gate] '

_installed = False
_handler = None
_orig_enqueue = None
_orig_enter_random = None
_fight_button = None  # dict describing LobbyHeader patch state
_last_handler_at = 0.0
_HANDLER_COOLDOWN_SEC = 5.0
_in_enqueue = False
_exit_queue_at = 0.0
_EXIT_QUEUE_COOLDOWN_SEC = 3.0
_prequeue_patched = False


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
    global _last_handler_at
    if _handler is None:
        _log('join requested vehInvID=%s arenaTypeID=%s (no handler)' % (
            veh_inv_id, arena_type_id))
        return False
    now = time.time()
    if (now - _last_handler_at) < _HANDLER_COOLDOWN_SEC:
        _log('handler cooldown; skip (vehInvID=%s)' % veh_inv_id)
        return False
    _last_handler_at = now
    try:
        _handler(veh_inv_id, arena_type_id)
        return True
    except Exception as exc:
        _log('handler failed: %s' % exc)
        return False


def _intercepted_enqueue(requestID, args):
    global _in_enqueue
    # Re-entrancy: exitFromQueue / respond must never re-enter enqueue.
    if _in_enqueue:
        _log('CMD_ENQUEUE re-entered; ignore')
        return
    _in_enqueue = True
    try:
        arr = args[0] if args else []
        veh_inv_id = arr[1] if len(arr) > 1 else None
        arena_type_id = arr[3] if len(arr) > 3 else 0
        _log('intercepted CMD_ENQUEUE vehInvID=%s arenaTypeID=%s' % (
            veh_inv_id, arena_type_id))
        dismiss_joining_ui()
        try:
            _respond_success(requestID)
        except Exception as exc:
            _log('respond failed: %s' % exc)
        _call_handler(veh_inv_id, arena_type_id)
    finally:
        _in_enqueue = False


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
    global _in_enqueue
    if _in_enqueue:
        _log('enterRandom re-entered; ignore')
        return False
    _in_enqueue = True
    try:
        _log('intercepted battle.enterRandom vehInvID=%s arenaTypeID=%s' % (
            vehInvID, arenaTypeID))
        dismiss_joining_ui()
        _call_handler(vehInvID, arenaTypeID)
    finally:
        _in_enqueue = False
    return False


def _wrapped_fight_click(header, map_id=None, action_name=None):
    """Earliest Battle! click — never fall through to stock joining screen."""
    global _in_enqueue
    if _in_enqueue:
        _log('fightClick re-entered; ignore')
        return None
    _in_enqueue = True
    try:
        _log('fightClick map_id=%s action=%s' % (map_id, action_name))
        dismiss_joining_ui()
        veh = None
        arena = 0
        try:
            if header is not None:
                veh = getattr(header, 'selectedVehicleInvID', None)
        except Exception:
            pass
        _call_handler(veh, arena)
    finally:
        _in_enqueue = False
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
        'gui.Scaleform.daapi.view.lobby.header.header',
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
            for attr in ('LobbyHeader', 'LobbyHeaderMeta', 'Header'):
                found = getattr(module, attr, None)
                if isinstance(found, type):
                    return found

    # After lobby load, scan already-imported modules for fightClick owner.
    try:
        import sys
        for name, module in list(sys.modules.items()):
            if module is None:
                continue
            for attr in ('LobbyHeader', 'LobbyHeaderMeta'):
                found = getattr(module, attr, None)
                if isinstance(found, type) and callable(
                        getattr(found, 'fightClick', None)):
                    _log('found %s via sys.modules[%s]' % (attr, name))
                    return found
            # The module itself may be the class (rare).
            if isinstance(module, type) and callable(
                    getattr(module, 'fightClick', None)):
                _log('found fightClick on sys.modules type %s' % name)
                return module
    except Exception:
        pass
    return None


def exit_stock_queue():
    """Dismiss stock random-queue joining UI.

    CRITICAL: exitFromQueue TOGGLES by queue state. Calling it while not
    queued re-enters queue() → CMD_ENQUEUE → this hook → recursion (log
    showed maximum recursion depth exceeded and a hung client).
    """
    global _exit_queue_at
    now = time.time()
    if (now - _exit_queue_at) < _EXIT_QUEUE_COOLDOWN_SEC:
        return False
    try:
        import BigWorld
        from gui.prb_control.dispatcher import g_prbLoader
    except Exception as exc:
        _log('exit_stock_queue imports failed: %s' % exc)
        return False
    try:
        dispatcher = g_prbLoader.getDispatcher()
        if dispatcher is None:
            return False
        player = BigWorld.player()
        in_queue = bool(getattr(player, 'isInRandomQueue', False))
        # Never call exitFromQueue unless we are actually queued.
        if not in_queue:
            return False
        entity = dispatcher.getEntity()
        exit_from_queue = getattr(entity, 'exitFromQueue', None)
        if not callable(exit_from_queue):
            return False
        _exit_queue_at = now
        exit_from_queue()
        _log('exit_stock_queue: exitFromQueue called')
        return True
    except Exception as exc:
        _log('exit_stock_queue failed: %s' % exc)
        return False


def hide_waiting_overlay():
    """Dismiss stock joining/waiting UI (gui.Scaleform.Waiting)."""
    try:
        from gui.Scaleform import Waiting
        hide = getattr(Waiting, 'hide', None)
        if callable(hide):
            try:
                hide()
            except TypeError:
                try:
                    hide('join')
                except Exception as exc2:
                    _log('Waiting.hide(join) failed: %s' % exc2)
                    return False
            except Exception as exc:
                _log('Waiting.hide failed: %s' % exc)
                return False
            _log('Waiting.hide() ok')
            return True
        # 2.3.1.2 Waiting may expose only module-level functions.
        hide_fn = getattr(Waiting, 'hide', None)
        if hide_fn is None and hasattr(Waiting, '__name__'):
            _log('Waiting.hide not callable')
    except Exception as exc:
        _log('Waiting import/hide failed: %s' % exc)
    return False


def dismiss_joining_ui():
    """Best-effort close of joining surfaces. Safe to call often."""
    exit_stock_queue()
    # Waiting.hide is cheap and does not toggle queue state.
    try:
        hide_waiting_overlay()
    except Exception:
        pass


def _patch_prequeue_queue():
    """Stop stock Random pre-queue from opening the joining screen.

    fightClick still runs on 2.3.1.2 (LobbyHeader not importable). It leads
    to BasePreQueueEntity.queue → Account enqueue. Patching queue() closes
    the joining UI path before Flash loads BATTLE_QUEUE.
    """
    global _prequeue_patched
    if _prequeue_patched:
        return False
    paths = (
        'gui.prb_control.entities.random.pre_queue.entity',
        'gui.prb_control.entities.base.pre_queue.entity',
    )
    try:
        import importlib
    except Exception:
        return False
    patched = False
    for path in paths:
        try:
            module = importlib.import_module(path)
        except Exception as exc:
            _log('prequeue import %s failed: %s' % (path, exc))
            continue
        for name in dir(module):
            if name.startswith('_'):
                continue
            cls = getattr(module, name, None)
            if not isinstance(cls, type):
                continue
            original = cls.__dict__.get('queue')
            if not callable(original):
                continue

            def _make_wrapper(orig):
                def _wrapped(self, *args, **kwargs):
                    _log('prequeue.queue blocked on %s' % type(self).__name__)
                    dismiss_joining_ui()
                    _call_handler(None, 0)
                    # Do not call orig: that opens stock joining + enqueue.
                    return None
                return _wrapped

            try:
                cls.queue = _make_wrapper(original)
            except Exception as exc:
                _log('patch %s.queue failed: %s' % (name, exc))
                continue
            _log('patched %s.queue on %s' % (path, name))
            patched = True
            _prequeue_patched = True
    return patched


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

    # --- Stock pre-queue (prevents joining screen on fightClick) ---
    if _patch_prequeue_queue():
        patched_any = True

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
    'exit_stock_queue',
    'dismiss_joining_ui',
    'set_handler',
    'handler',
]
