# -*- coding: utf-8 -*-
"""Path resolution for the launcher (workspace root, game root, starter)."""
from __future__ import absolute_import, division, print_function

import os

DEFAULT_GAME_ROOT = os.path.normpath(
    r'D:\WOT\World_of_Tanks_EU_Offline_2.3.1.2')
STARTER_NAME = 'vvg_worker_starter.exe'

# Prefer workspace-relative layout over the installed package layout.
_HERE = os.path.dirname(os.path.abspath(__file__))
_CANDIDATE_ROOTS = (
    os.path.abspath(os.path.join(_HERE, '..', '..')),  # src/launcher -> root
    os.path.abspath(os.path.join(_HERE, '..', '..', '..')),
)


def workspace_root():
    """Locate the vvg-offline-battles workspace root (must contain src/)."""
    for root in _CANDIDATE_ROOTS:
        if os.path.isdir(os.path.join(root, 'src', 'sim_worker')):
            return root
    # Fallback: package parent's parent if layout matches loosely.
    return _CANDIDATE_ROOTS[0]


def game_root(explicit=None):
    if explicit:
        return os.path.normpath(explicit)
    env = (os.environ.get('VVG_GAME_ROOT') or '').strip()
    if env:
        return os.path.normpath(env)
    return DEFAULT_GAME_ROOT


def starter_exe(root=None):
    """Path to vvg_worker_starter.exe under the game win64/ dir."""
    root = game_root(root)
    return os.path.join(root, 'win64', STARTER_NAME)


def sim_worker_src(root=None):
    """Absolute path to the workspace src/ directory (for PYTHONPATH)."""
    root = root or workspace_root()
    return os.path.join(root, 'src')


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)
    return path
