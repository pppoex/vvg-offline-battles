"""Python interface for the WoT 2.3.1.2 x64 multi-client instance guard.

Environment:
    VVG_ALLOW_MULTIPLE_CLIENTS=1  enables release_if_requested()

The native bridge is a ctypes-loadable x64 DLL/pyd that:
  - validates the host PE identity (timestamp / image base / size)
  - releases named WOT_STARTUP_MUTEX / WGC AppMutex objects owned by this process
  - hides/restores process windows for hidden workers

Unlike 0.9.22, atmosphere-owner patching is not mapped yet (native status 22).
"""
from __future__ import print_function

import os
import sys

ALLOW_MULTIPLE_CLIENTS_ENV = 'VVG_ALLOW_MULTIPLE_CLIENTS'
NATIVE_MODULE_NAME = 'vvg_instance_guard_native'
NATIVE_FILENAME = NATIVE_MODULE_NAME + '.pyd'
GAME_VERSION_DIR = '2.3.1.2'

# Native status codes from instance_guard.c
GUARD_STATUS_HOST_MISMATCH = 1
GUARD_STATUS_NOT_INITIALIZED = 21
GUARD_STATUS_ATMOSPHERE_UNSUPPORTED = 22
GUARD_STATUS_MUTEX_STILL_EXISTS = 16

_GUARD_STATUS_OPERATIONS = {
    1: 'host PE identity validation',
    2: 'python27.dll lookup',
    3: 'python27.dll symbol resolve',
    16: 'startup/WGC mutex still present',
    17: 'mutex probe failed',
    18: 'handle enumeration failed',
    19: 'no target mutexes',
    20: 'mutex close partial',
    21: 'native bridge not initialized',
    22: 'atmosphere guard unsupported on 2.3.1.2',
}

_attempted = False
_release_succeeded = False
_release_error = None
_native_bridge = None


class ClientInstanceGuardError(RuntimeError):
    """The 2.3.1.2 client guard could not be released or loaded safely."""

    def __init__(self, operation, error_code):
        self.operation = operation
        self.error_code = int(error_code)
        RuntimeError.__init__(
            self, '%s failed with native status %d' % (
                self.operation, self.error_code))


def _multiple_clients_requested(environ):
    value = environ.get(ALLOW_MULTIPLE_CLIENTS_ENV)
    try:
        value = value.strip()
    except AttributeError:
        return False
    return value == '1'


def _unique_existing_paths(candidates):
    seen = set()
    ordered = []
    for path in candidates:
        if not path:
            continue
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return ordered


def _native_bridge_path(executable=None, extra_search=None):
    """Resolve the sidecar path for 2.3.1.2 (exe lives under win64/).

    Search order:
      1. VVG_INSTANCE_GUARD_PATH env override
      2. next to the running executable (win64/vvg_instance_guard_native.pyd)
      3. <install root>/mods/<version>/  (sibling of win64/)
      4. cwd and parent of cwd (game often starts with cwd = game root)
      5. optional extra_search paths (tests / launcher drops)
    """
    override = os.environ.get('VVG_INSTANCE_GUARD_PATH')
    if override:
        return override

    if executable is None:
        executable = sys.executable

    bases = []
    if executable:
        try:
            exe_dir = os.path.dirname(os.path.abspath(executable))
            if exe_dir:
                bases.append(exe_dir)
                if os.path.basename(exe_dir).lower() == 'win64':
                    bases.append(os.path.dirname(exe_dir))
        except (TypeError, ValueError, OSError):
            pass

    try:
        cwd = os.path.abspath(os.getcwd())
        bases.append(cwd)
        bases.append(os.path.dirname(cwd))
    except (TypeError, ValueError, OSError):
        pass

    candidates = []
    for base in bases:
        candidates.append(os.path.join(base, NATIVE_FILENAME))
        candidates.append(
            os.path.join(base, 'mods', GAME_VERSION_DIR, NATIVE_FILENAME))
        candidates.append(os.path.join(base, 'win64', NATIVE_FILENAME))
        # Walk one more level: win64/../mods is already covered; also try
        # install-root/mods when cwd is deeper.
        parent = os.path.dirname(base)
        if parent and parent != base:
            candidates.append(
                os.path.join(parent, 'mods', GAME_VERSION_DIR, NATIVE_FILENAME))

    if extra_search:
        for base in extra_search:
            candidates.append(os.path.join(base, NATIVE_FILENAME))
            candidates.append(
                os.path.join(base, 'vvg_instance_guard_native.dll'))

    candidates = _unique_existing_paths(candidates)
    for path in candidates:
        if os.path.isfile(path):
            return path
    # Prefer the install-root mods path as the stable default when nothing
    # exists yet (first deploy).
    for base in bases:
        if os.path.basename(base).lower() == 'win64':
            return os.path.join(
                os.path.dirname(base), 'mods', GAME_VERSION_DIR, NATIVE_FILENAME)
    return candidates[0] if candidates else NATIVE_FILENAME


class _NativeBridge(object):
    """Thin ctypes wrapper around the x64 native exports."""

    def __init__(self, dll):
        import ctypes
        self._dll = dll
        dll.vvg_init_bridge.restype = ctypes.c_int
        dll.vvg_init_bridge.argtypes = []
        for name in (
                'vvg_release_client_guard',
                'vvg_probe_startup_mutex',
                'vvg_install_atmosphere_owner_guard',
                'vvg_hide_process_windows',
                'vvg_show_process_windows',
                'vvg_validate_host'):
            fn = getattr(dll, name)
            fn.restype = ctypes.c_long
            fn.argtypes = []

    def init_bridge(self):
        return int(self._dll.vvg_init_bridge())

    def validate_host(self):
        return int(self._dll.vvg_validate_host())

    def release_client_guard(self):
        return int(self._dll.vvg_release_client_guard())

    def probe_startup_mutex(self):
        return int(self._dll.vvg_probe_startup_mutex())

    def install_atmosphere_owner_guard(self):
        return int(self._dll.vvg_install_atmosphere_owner_guard())

    def hide_process_windows(self):
        return int(self._dll.vvg_hide_process_windows())

    def show_process_windows(self):
        return int(self._dll.vvg_show_process_windows())


def _load_native_bridge(path=None, imp_module=None):
    global _native_bridge
    if _native_bridge is not None:
        return _native_bridge
    path = _native_bridge_path() if path is None else path
    if not os.path.isfile(path):
        raise ImportError('native instance guard bridge is missing: %s' % path)

    import ctypes
    try:
        dll = ctypes.CDLL(path)
    except OSError as error:
        raise ImportError(
            'native instance guard bridge failed to load (%s): %s' % (
                path, error))

    bridge = _NativeBridge(dll)

    # Outside the game host PE (unit tests) vvg_validate_host may fail; still
    # allow construction so pure logic can be exercised. Inside the game the
    # PE must match before any release is attempted.
    host_status = bridge.validate_host()
    init_status = bridge.init_bridge()
    if host_status != 0 and init_status == 0:
        # Not running under the exact client image. Keep the object so unit
        # tests can call probe/validate; release will refuse via status 21.
        _native_bridge = bridge
        return bridge
    if init_status == 0 and host_status == 0:
        raise ClientInstanceGuardError('native bridge init', GUARD_STATUS_NOT_INITIALIZED)

    _native_bridge = bridge
    return bridge


def _raise_release_failure(status):
    status = int(status)
    operation = _GUARD_STATUS_OPERATIONS.get(
        status, NATIVE_MODULE_NAME)
    raise ClientInstanceGuardError(operation, status)


def _release_native(native_bridge=None):
    if native_bridge is None:
        native_bridge = _load_native_bridge()
    status = int(native_bridge.release_client_guard())
    if status != 0:
        _raise_release_failure(status)
    return True


def _window_operation(method_name, native_bridge=None):
    if native_bridge is None:
        native_bridge = _load_native_bridge()
    result = int(getattr(native_bridge, method_name)())
    if result < 0:
        raise ClientInstanceGuardError(method_name, -result)
    return result


def hide_process_windows(native_bridge=None):
    """Hide and remember this process's visible top-level windows."""
    return _window_operation('hide_process_windows', native_bridge)


def show_process_windows(native_bridge=None):
    """Restore top-level windows hidden through this bridge."""
    return _window_operation('show_process_windows', native_bridge)


def probe_startup_mutex(native_bridge=None):
    """Return native status 0 when target mutex names are absent."""
    if native_bridge is None:
        native_bridge = _load_native_bridge()
    return int(native_bridge.probe_startup_mutex())


def release_if_requested(environ=None, releaser=None):
    """Release startup/WGC mutexes once for an opted-in process."""
    global _attempted, _release_error, _release_succeeded

    environ = os.environ if environ is None else environ
    if not _multiple_clients_requested(environ):
        return False
    if _attempted:
        if _release_error is not None:
            raise _release_error
        return _release_succeeded

    _attempted = True
    try:
        if releaser is None:
            releaser = _release_native
        _release_succeeded = bool(releaser())
        if not _release_succeeded:
            raise ClientInstanceGuardError('client guard release', 0)
        return True
    except Exception as error:
        _release_error = error
        raise


def reset_state_for_tests():
    """Test-only helper to clear module singleton state."""
    global _attempted, _release_error, _release_succeeded, _native_bridge
    _attempted = False
    _release_error = None
    _release_succeeded = False
    _native_bridge = None
