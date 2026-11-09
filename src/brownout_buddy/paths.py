"""Per-user config and database locations. Nothing here is uploaded."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from brownout_buddy.config import Config


def default_config_dir() -> Path:
    if os.name == "nt":
        root = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(root) / "BrownoutBuddy"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BrownoutBuddy"
    root = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(root) / "brownout-buddy"


def default_config_path() -> Path:
    return default_config_dir() / "config.toml"


def default_data_dir() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return Path(root) / "BrownoutBuddy"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BrownoutBuddy"
    root = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(root) / "brownout-buddy"


def default_db_path() -> Path:
    return default_data_dir() / "outages.sqlite"


def resolve_db_path(config: Config, explicit: str | None) -> Path:
    """``--db`` wins, then ``BROWNOUT_BUDDY_DB``, then ``store.path``, then the default."""

    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("BROWNOUT_BUDDY_DB")
    if env:
        return Path(env).expanduser()
    if config.store_path:
        path = Path(config.store_path).expanduser()
        if not path.is_absolute() and config.config_path is not None:
            path = config.config_path.parent / path
        return path
    return default_db_path()
