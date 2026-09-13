# -*- coding: utf-8 -*-
"""Start / supervise the authoritative sim-worker process."""
from __future__ import absolute_import, division, print_function

import signal
import subprocess
import sys
import threading
import time

from launcher import env as envmod
from launcher import paths as pathmod
from launcher import ports


def build_server_command(host, port, map_name=None, tick_hz=None,
                         snapshot_hz=None, python=None):
    python = python or sys.executable
    cmd = [
        python, '-m', 'sim_worker.main',
        '--host', str(host),
        '--port', str(port),
    ]
    if map_name:
        cmd.extend(['--map', str(map_name)])
    if tick_hz is not None:
        cmd.extend(['--tick-hz', str(tick_hz)])
    if snapshot_hz is not None:
        cmd.extend(['--snapshot-hz', str(snapshot_hz)])
    return cmd


def start_server_process(host, port, map_name=None, tick_hz=None,
                         snapshot_hz=None, python=None, workspace=None,
                         log=None):
    """Spawn sim-worker in a child process. Returns the Popen handle."""
    log = log or ports.log
    workspace = workspace or pathmod.workspace_root()
    src = pathmod.sim_worker_src(workspace)
    overlay = envmod.server_env(host=host, port=port, pythonpath=src)
    child_env = envmod.base_env(overlay)
    cmd = build_server_command(
        host, port, map_name=map_name, tick_hz=tick_hz,
        snapshot_hz=snapshot_hz, python=python)
    log('starting sim-worker: %s' % ' '.join(cmd))
    log('cwd=%s PYTHONPATH=%s' % (workspace, src))
    proc = subprocess.Popen(cmd, cwd=workspace, env=child_env)
    log('sim-worker pid=%s' % proc.pid)
    return proc


def run_server(host, port, map_name=None, tick_hz=None, snapshot_hz=None,
               kill_port=False, ready_timeout=15.0, python=None,
               workspace=None):
    """Block until the server is listening; then wait for Ctrl+C / exit.

    Returns process exit code (0 on clean shutdown).
    """
    log = ports.log
    host = host or envmod.DEFAULT_SERVER_HOST
    port = int(port if port is not None else envmod.DEFAULT_SERVER_PORT)

    if not ports.require_port_free(host, port, kill=kill_port, log=log):
        return 2

    proc = start_server_process(
        host, port, map_name=map_name, tick_hz=tick_hz,
        snapshot_hz=snapshot_hz, python=python, workspace=workspace, log=log)

    stop_lock = threading.Lock()
    stopping = {'done': False}

    def _terminate():
        with stop_lock:
            if stopping['done'] or proc.poll() is not None:
                stopping['done'] = True
                return
            stopping['done'] = True
            log('stopping sim-worker pid=%s' % proc.pid)
            try:
                if hasattr(signal, 'CTRL_BREAK_EVENT'):
                    # Create-nothing console — plain terminate is fine.
                    pass
                proc.terminate()
            except OSError:
                pass
            try:
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                except OSError:
                    pass

    def _on_signal(signum, frame):
        log('signal %s received' % signum)
        _terminate()

    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[sig] = signal.signal(sig, _on_signal)
        except (ValueError, OSError):
            pass

    try:
        if not ports.wait_for_port(host, port, timeout=ready_timeout):
            log('ERROR: sim-worker did not open %s:%s within %ss'
                % (host, port, ready_timeout))
            _terminate()
            return 3
        log('sim-worker listening on %s:%s' % (host, port))
        log('press Ctrl+C to stop')
        while True:
            code = proc.poll()
            if code is not None:
                log('sim-worker exited with code %s' % code)
                return int(code) if code is not None else 0
            time.sleep(0.3)
    except KeyboardInterrupt:
        log('keyboard interrupt')
        _terminate()
        return 0
    finally:
        for sig, handler in previous.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass
        if proc.poll() is None:
            _terminate()
