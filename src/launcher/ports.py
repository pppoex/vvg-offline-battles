# -*- coding: utf-8 -*-
"""TCP port helpers: is-anyone-listening and optional kill of local owner."""
from __future__ import absolute_import, division, print_function

import os
import re
import socket
import subprocess
import sys
import time

_HOST = '127.0.0.1'


def is_port_open(host, port, timeout=0.4):
    """True if a TCP connect to host:port succeeds (something is listening)."""
    try:
        sock = socket.create_connection((host or _HOST, int(port)), timeout)
    except (socket.error, socket.timeout, OSError, ValueError):
        return False
    try:
        sock.close()
    except Exception:
        pass
    return True


def wait_for_port(host, port, timeout=15.0, interval=0.2):
    """Poll until host:port accepts a connection. Returns True/False."""
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        if is_port_open(host, port):
            return True
        time.sleep(interval)
    return False


def _netstat_pids(port):
    """Best-effort: local PIDs bound to *port* via netstat -ano."""
    cmd = ['netstat', '-ano', '-p', 'tcp']
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = proc.communicate()
    except OSError:
        return []
    if not out:
        return []
    if not isinstance(out, str):
        text = out.decode('utf-8', 'replace')
    else:
        text = out
    pids = []
    # Lines like: TCP    127.0.0.1:28782    0.0.0.0:0    LISTENING    12345
    pattern = re.compile(
        r'^\s*TCP\s+\S*:(\d+)\s+\S+:\d+\s+LISTENING\s+(\d+)\s*$',
        re.IGNORECASE)
    port_s = str(int(port))
    for line in text.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        if match.group(1) != port_s:
            continue
        pid = int(match.group(2))
        if pid > 0 and pid != os.getpid():
            pids.append(pid)
    return pids


def list_port_owners(host, port):
    """Return local PIDs believed to listen on *port* (may be empty)."""
    return _netstat_pids(port)


def kill_port_owners(host, port):
    """Force-kill local processes listening on *port*.

    Returns the list of PIDs terminated. Raises RuntimeError when any kill fails.
    """
    pids = _netstat_pids(port)
    if not pids:
        return []
    failed = []
    for pid in pids:
        # /T kills the tree (starter may own child python.exe).
        code = subprocess.call(
            ['taskkill', '/PID', str(pid), '/T', '/F'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if code != 0:
            failed.append(pid)
    if failed:
        raise RuntimeError(
            'failed to kill pid(s) on port %s: %s' % (port, failed))
    # Give the OS a moment to release the bind.
    for _ in range(20):
        if not is_port_open(host, port, timeout=0.2):
            return pids
        time.sleep(0.15)
    return pids


def require_port_free(host, port, kill=False, log=None):
    """Ensure host:port is free. Optionally kill occupants first."""
    if not is_port_open(host, port):
        return True
    owners = list_port_owners(host, port)
    owner_note = ' pids=%s' % owners if owners else ''
    if kill:
        if log:
            log('port %s:%s occupied%s — --kill-port, terminating'
                % (host, port, owner_note))
        killed = kill_port_owners(host, port)
        if log:
            log('killed pid(s): %s' % killed)
        if is_port_open(host, port, timeout=0.5):
            return False
        return True
    if log:
        log('ERROR: port %s:%s already in use%s' % (host, port, owner_note))
        log('hint: re-run with --kill-port, or stop the old sim-worker first')
    return False


def log(message):
    sys.stdout.write('[launcher] %s\n' % message)
    sys.stdout.flush()
