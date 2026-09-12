# -*- coding: utf-8 -*-
"""配置管理 — 从 Offline2.3.1.2 config.py 适配为联机架构。

保留：JSON override 加载 + _get 类型推断。
移除：全部单机假服务器 / OFFLINE_* 配置。
新增：SERVER_* / CLIENT_MODE / 与 sim-worker 相关的网络默认值。
"""
from __future__ import absolute_import, division, print_function

import json
import os
import sys

_CONFIG_FILE_NAME = 'vvg_config.json'
_json_overrides = {}
_search_dirs = []
_json_path = None
_loaded = False


def _default_search_dirs():
    dirs = []
    try:
        dirs.append(os.getcwd())
    except Exception:
        pass
    try:
        mod = sys.modules.get(__name__)
        if mod and hasattr(mod, '__file__') and mod.__file__:
            dirs.insert(0, os.path.dirname(os.path.abspath(mod.__file__)))
    except Exception:
        pass
    # 工作区根 / res_mods 下的附属配置
    try:
        cwd = os.getcwd()
        dirs.append(cwd)
        for candidate in (
            os.path.join(cwd, 'res_mods'),
            os.path.join(cwd, 'config'),
        ):
            if os.path.isdir(candidate):
                dirs.append(candidate)
    except Exception:
        pass
    return dirs


def _find_config_file():
    for directory in _search_dirs:
        candidate = os.path.join(directory, _CONFIG_FILE_NAME)
        if os.path.isfile(candidate):
            return candidate
        # 兼容旧名
        legacy = os.path.join(directory, 'config.json')
        if os.path.isfile(legacy) and 'vvg' in directory.lower():
            return legacy
    return None


def load_overrides(force=False):
    """扫描搜索路径并加载 JSON 覆盖。幂等；force=True 时强制重载。"""
    global _json_path, _loaded
    if _loaded and not force:
        return _json_path

    _json_overrides.clear()
    _search_dirs[:] = _default_search_dirs()

    path = _find_config_file()
    _json_path = path
    if path:
        try:
            with open(path, 'r') as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if not str(key).startswith('_comment'):
                        _json_overrides[key] = value
            print('[VVG/Config] overrides from: %s' % path)
        except Exception as exc:
            print('[VVG/Config] JSON load error: %s' % exc)
    _loaded = True
    return _json_path


def _get(key, default_value):
    """读取覆盖值，并按 default_value 的类型做粗转换。"""
    if not _loaded:
        load_overrides()
    val = _json_overrides.get(key, default_value)
    if val is not None and default_value is not None:
        try:
            if isinstance(default_value, bool):
                return bool(val)
            if isinstance(default_value, int) and not isinstance(default_value, bool):
                return int(val)
            if isinstance(default_value, float):
                return float(val)
        except (ValueError, TypeError):
            pass
    return val


# ---------------------------------------------------------------------------
# 网络 / 会话（联机架构核心）
# ---------------------------------------------------------------------------

# sim-worker 默认监听地址（单机也连本地）
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 28782

# 'player' | 'worker'
CLIENT_MODE = 'player'

# 与 multiclient 守卫环境变量 VVG_ALLOW_MULTIPLE_CLIENTS 对齐的默认开关
# （真正生效仍以启动器 / 环境变量为准）
ALLOW_MULTIPLE_CLIENTS = True

# 快照广播相关（参考 0.9.22：服务器 30 Hz，快照 15 Hz）
SERVER_TICK_HZ = 30
SNAPSHOT_HZ = 15

# 断线重连
RECONNECT_ENABLED = True
RECONNECT_MAX_ATTEMPTS = 10
RECONNECT_INITIAL_DELAY = 0.5
RECONNECT_BACKOFF = 2.0
RECONNECT_MAX_DELAY = 8.0

# 客户端预测
PREDICTION_ENABLED = True
INTERP_BUFFER_MS = 100

# 日志
LOG_NAME = 'vvg_client.log'

# 协议（与 src/protocol/constants.py 保持一致；此处仅作客户端侧默认）
PROTOCOL_VERSION = 5
JSONLINES_DELIMITER = b'\n'


# ---------------------------------------------------------------------------
# 访问器
# ---------------------------------------------------------------------------

def get_server_address():
    """返回 (host, port)。"""
    return (
        _get('SERVER_HOST', SERVER_HOST),
        int(_get('SERVER_PORT', SERVER_PORT)),
    )


def get_client_mode():
    mode = str(_get('CLIENT_MODE', CLIENT_MODE)).lower()
    if mode not in ('player', 'worker'):
        mode = 'player'
    return mode


def get_reconnect_policy():
    """返回重连策略 dict。"""
    return {
        'enabled': bool(_get('RECONNECT_ENABLED', RECONNECT_ENABLED)),
        'max_attempts': int(_get('RECONNECT_MAX_ATTEMPTS', RECONNECT_MAX_ATTEMPTS)),
        'initial_delay': float(_get('RECONNECT_INITIAL_DELAY', RECONNECT_INITIAL_DELAY)),
        'backoff': float(_get('RECONNECT_BACKOFF', RECONNECT_BACKOFF)),
        'max_delay': float(_get('RECONNECT_MAX_DELAY', RECONNECT_MAX_DELAY)),
    }


def get_tick_rates():
    return {
        'server_hz': int(_get('SERVER_TICK_HZ', SERVER_TICK_HZ)),
        'snapshot_hz': int(_get('SNAPSHOT_HZ', SNAPSHOT_HZ)),
    }


def reset_for_tests():
    """仅用于单元测试。"""
    global _loaded, _json_path
    _json_overrides.clear()
    _search_dirs[:] = []
    _json_path = None
    _loaded = False


def is_loaded():
    return _loaded


def current_json_path():
    return _json_path
