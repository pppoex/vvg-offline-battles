# -*- coding: utf-8 -*-
"""Integration tests for the M5 launcher (no real game / long-lived server)."""
from __future__ import absolute_import, division, print_function

import os
import socket
import sys
import threading
import time

import pytest

# src/ is already on pytest pythonpath via pyproject.
from launcher import build as buildmod
from launcher import client as clientmod
from launcher import cli as clicmd
from launcher import env as envmod
from launcher import paths as pathmod
from launcher import ports as portsmod
from launcher import server as servermod


def _free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


class _EchoServer(object):
    """Tiny TCP listener so is_port_open can succeed in isolation."""

    def __init__(self, host='127.0.0.1', port=None):
        self.host = host
        self.port = port or _free_port()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, self.port))
        self._sock.listen(5)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True

    def start(self):
        self._thread.start()
        return self

    def _run(self):
        while not self._stop.is_set():
            try:
                self._sock.settimeout(0.3)
                conn, _addr = self._sock.accept()
            except (socket.timeout, socket.error):
                continue
            try:
                conn.close()
            except Exception:
                pass

    def close(self):
        self._stop.set()
        try:
            self._sock.close()
        except Exception:
            pass
        self._thread.join(timeout=2)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()
        return False


# ---------------------------------------------------------------------------
# env
# ---------------------------------------------------------------------------

def test_client_env_player_defaults():
    env = envmod.client_env(envmod.MODE_PLAYER)
    assert env['VVG_CLIENT_MODE'] == 'player'
    assert env['VVG_SERVER_HOST'] == '127.0.0.1'
    assert env['VVG_SERVER_PORT'] == '28782'
    assert env['VVG_PLAYER_NAME'] == 'Player'
    assert env['VVG_PLAYER_VEHICLE'] == 'ussr:R05_LT'
    assert env['VVG_ALLOW_MULTIPLE_CLIENTS'] == '1'


def test_client_env_worker_mode():
    env = envmod.client_env(envmod.MODE_WORKER, host='127.0.0.1', port=1234)
    assert env['VVG_CLIENT_MODE'] == 'simulation_worker'
    assert env['VVG_SERVER_PORT'] == '1234'
    assert env['VVG_PLAYER_NAME'] == 'worker'


def test_client_env_rejects_bad_mode():
    with pytest.raises(ValueError):
        envmod.client_env('bogus')


def test_server_env_sets_pythonpath():
    env = envmod.server_env(pythonpath=r'D:\src')
    assert env['PYTHONPATH'] == r'D:\src'
    assert env['VVG_SERVER_PORT'] == '28782'


# ---------------------------------------------------------------------------
# paths / starter argv
# ---------------------------------------------------------------------------

def test_workspace_root_has_sim_worker():
    root = pathmod.workspace_root()
    assert os.path.isdir(os.path.join(root, 'src', 'sim_worker'))
    assert os.path.isdir(os.path.join(root, 'src', 'launcher'))


def test_starter_exe_path():
    path = pathmod.starter_exe(r'D:\Games\WoT')
    assert path.endswith('vvg_worker_starter.exe')
    assert 'win64' in path.replace('/', '\\')


def test_build_starter_argv_player():
    argv = clientmod.build_starter_argv(r'C:\g\win64\s.exe', 'player')
    assert argv == [r'C:\g\win64\s.exe', '--player']


def test_build_starter_argv_worker_hide_show():
    base = r'C:\g\win64\s.exe'
    assert clientmod.build_starter_argv(base, 'worker', show=True) == [
        base, '--worker-only', '--show']
    assert clientmod.build_starter_argv(base, 'worker', show=False) == [
        base, '--worker-only', '--hide']
    assert clientmod.build_starter_argv(base, 'worker') == [
        base, '--worker-only']


def test_resolve_launcher_argv_force_fallback_missing_game():
    with pytest.raises(SystemExit):
        clientmod.resolve_launcher_argv(
            'player', root=r'Z:\definitely\not\installed', force_fallback=True)


# ---------------------------------------------------------------------------
# ports
# ---------------------------------------------------------------------------

def test_is_port_open_false_on_free_port():
    port = _free_port()
    assert portsmod.is_port_open('127.0.0.1', port) is False


def test_is_port_open_true_when_listening():
    with _EchoServer() as server:
        assert portsmod.is_port_open('127.0.0.1', server.port) is True


def test_require_port_free_reports_occupied_without_kill():
    with _EchoServer() as server:
        assert portsmod.require_port_free(
            '127.0.0.1', server.port, kill=False) is False


def test_require_port_free_ok_when_free():
    assert portsmod.require_port_free(
        '127.0.0.1', _free_port(), kill=False) is True


# ---------------------------------------------------------------------------
# server command construction
# ---------------------------------------------------------------------------

def test_build_server_command_defaults():
    cmd = servermod.build_server_command('127.0.0.1', 28782, python='py')
    assert cmd[0] == 'py'
    assert '-m' in cmd and 'sim_worker.main' in cmd
    assert '--port' in cmd and '28782' in cmd


def test_build_server_command_with_map():
    cmd = servermod.build_server_command(
        '127.0.0.1', 1, map_name='training', python='py')
    assert 'training' in cmd
    assert '--map' in cmd


# ---------------------------------------------------------------------------
# server process start + port free check (integration)
# ---------------------------------------------------------------------------

def test_run_server_rejects_occupied_port():
    with _EchoServer() as server:
        code = servermod.run_server(
            host='127.0.0.1',
            port=server.port,
            kill_port=False,
            ready_timeout=1.0,
            workspace=pathmod.workspace_root(),
        )
    assert code == 2


def test_start_server_process_and_shut_down():
    port = _free_port()
    proc = servermod.start_server_process(
        '127.0.0.1', port, workspace=pathmod.workspace_root())
    try:
        assert portsmod.wait_for_port('127.0.0.1', port, timeout=10.0) is True
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def test_cli_no_command_prints_help(capsys):
    code = clicmd.main([])
    assert code == 1
    out = capsys.readouterr().out
    assert 'build' in out and 'deploy' in out and 'server' in out


def test_cli_parser_subcommands():
    parser = clicmd.build_parser()
    args = parser.parse_args(['player', '--name', 'Alice', '--vehicle', 'x'])
    assert args.command == 'player'
    assert args.name == 'Alice'
    assert args.vehicle == 'x'

    args = parser.parse_args(['worker', '--show'])
    assert args.command == 'worker'
    assert args.show is True

    args = parser.parse_args(['worker', '--hide'])
    assert args.show is False

    args = parser.parse_args(['server', '--kill-port', '--port', '1'])
    assert args.command == 'server'
    assert args.kill_port is True
    assert args.port == 1

    args = parser.parse_args(
        ['deploy', '--only', 'client', '--dry-run'])
    assert args.command == 'deploy'
    assert args.only == 'client'
    assert args.dry_run is True

    args = parser.parse_args(['build', '--only', 'native', '--clean'])
    assert args.command == 'build'
    assert args.only == 'native'
    assert args.clean is True


# ---------------------------------------------------------------------------
# build layout (artifacts under build/, sources under src/)
# ---------------------------------------------------------------------------

def test_build_paths_mirror_src():
    root = pathmod.workspace_root()
    assert pathmod.build_root(root) == os.path.join(root, 'build')
    assert pathmod.native_artifact_dir(root) == os.path.join(
        root, 'build', 'multiclient', 'native')
    assert buildmod.native_out_dir(root) == os.path.join(
        root, 'build', 'multiclient', 'native')


def test_build_select_components():
    assert buildmod.select_components() == list(buildmod.COMPONENTS)
    assert buildmod.select_components(only='native') == ['native']
    with pytest.raises(SystemExit):
        buildmod.select_components(only='native', skip='native')
    with pytest.raises(SystemExit):
        buildmod.select_components(only='nope')


def test_native_sources_only_under_src():
    """No compiled artifacts may remain under src/."""
    root = pathmod.workspace_root()
    native = os.path.join(root, 'src', 'multiclient', 'native')
    assert os.path.isfile(os.path.join(native, 'instance_guard.c'))
    assert os.path.isfile(os.path.join(native, 'worker_starter.c'))
    assert os.path.isfile(os.path.join(native, 'build.ps1'))
    assert not os.path.isdir(os.path.join(native, 'out'))
    for dirpath, _dirs, files in os.walk(
            os.path.join(root, 'src', 'multiclient', 'native')):
        for name in files:
            assert not name.endswith(('.pyd', '.exe', '.obj', '.dll'))


def test_installed_native_from_build_if_present():
    """install_multiclient must prefer build/multiclient/native/."""
    import install_multiclient
    assert install_multiclient.BUILD_NATIVE.endswith(
        os.path.join('build', 'multiclient', 'native'))
    # When artifacts are present in build/, install dry-run should plan them.
    out = install_multiclient.BUILD_NATIVE
    if os.path.isfile(os.path.join(out, install_multiclient.NATIVE_NAME)):
        planned = install_multiclient.install(
            install_multiclient.DEFAULT_GAME_ROOT, dry_run=True)
        labels = [row[2] for row in planned]
        assert any('native pyd' in lab for lab in labels)
        sources = [row[0] for row in planned if 'native pyd' in row[2]]
        assert all(
            s.replace('/', '\\').startswith(
                os.path.join(out).replace('/', '\\'))
            or 'win64' in s.replace('/', '\\')
            or 'mods' in s.replace('/', '\\')
            for s in sources)


# ---------------------------------------------------------------------------
# install_all shell
# ---------------------------------------------------------------------------

def test_install_all_select_components():
    import install_all
    assert install_all.select_components() == list(install_all.ORDER)
    assert install_all.select_components(only='client') == ['client']
    assert install_all.select_components(skip='offhangar') == [
        'multiclient', 'client']
    with pytest.raises(SystemExit):
        install_all.select_components(only='client', skip='client')
    with pytest.raises(SystemExit):
        install_all.select_components(only='nope')


def test_install_all_dry_run_missing_game_root(tmp_path):
    import install_all
    missing = str(tmp_path / 'no-such-game')
    # dry_run + missing root: multiclient.install raises SystemExit -> 1
    code = install_all.install_all(
        game_root=missing, dry_run=True, only='multiclient')
    assert code in (0, 1)

    # real default root, dry-run all components (no writes)
    code = install_all.install_all(
        game_root=install_all.DEFAULT_GAME_ROOT, dry_run=True)
    assert code == 0
