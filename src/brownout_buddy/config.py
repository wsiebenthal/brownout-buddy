"""TOML configuration.

The annotated example lives in :data:`EXAMPLE_TOML` and is written to
``config.example.toml`` in the repository. ``load_config(None)`` uses the
same values as a successful load of that example (comments and whitespace
aside).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

VALID_COMMAND_EVENTS = frozenset(
    {
        "power_loss",
        "power_restore",
        "internet_down",
        "lan_down",
        "connectivity_restore",
    }
)


class ConfigError(Exception):
    """The config file is missing, unreadable, or invalid."""


@dataclass(frozen=True)
class ProbeConfig:
    host: str
    port: int


@dataclass(frozen=True)
class CommandConfig:
    """A user command. ``argv`` is executed without a shell."""

    on: str
    argv: tuple[str, ...]


@dataclass(frozen=True)
class Config:
    poll_interval_seconds: float = 5.0
    timezone: str = ""
    power_enabled: bool = True
    network_enabled: bool = True
    network_timeout_seconds: float = 2.0
    failure_threshold: int = 2
    recovery_threshold: int = 1
    use_default_route: bool = True
    lan_probes: tuple[ProbeConfig, ...] = ()
    internet_probes: tuple[ProbeConfig, ...] = (
        ProbeConfig("1.1.1.1", 443),
        ProbeConfig("8.8.8.8", 53),
    )
    command_timeout_seconds: float = 30.0
    pause_processes: tuple[str, ...] = ()
    dim_brightness: bool = False
    battery_saver: bool = False
    notify: bool = True
    commands: tuple[CommandConfig, ...] = ()
    store_path: str = ""
    tray_enabled: bool = True
    classifier_enabled: bool = True
    classifier_prompt_below: float = 0.6
    classifier_min_score: float = 0.55
    classifier_min_margin: float = 0.15
    light_enabled: bool = True
    sentinel_enabled: bool = False
    sentinel_host: str = ""
    sentinel_port: int = 9
    config_path: Path | None = None


EXAMPLE_TOML = """\
# Brownout Buddy configuration.
# Copy with `brownout-buddy init-config`, then edit the copy.
# Pass `--config` to use a file in any location.
# Keys you omit keep the defaults shown here.

# How often the live monitor checks power and the network, in seconds.
poll_interval_seconds = 5

# IANA timezone for history and stats, for example "Asia/Manila".
# Empty means the computer's local timezone.
timezone = ""

[power]
# Read the battery with psutil. When false, live monitoring will not open
# power outages. The simulator still can.
enabled = true

[network]
enabled = true
# TCP connect timeout for each probe, in seconds.
timeout_seconds = 2.0
# Consecutive changed polls before the network state sticks.
# Failures wait longer than recoveries so a single dropped probe does not
# open an outage, and coming back online is noticed quickly.
failure_threshold = 2
recovery_threshold = 1
# On Linux, a missing default route counts as LAN down when no LAN probes
# are configured. Other operating systems do not read the route table yet;
# add [[network.lan_probes]] there to separate a dead router from a dead ISP.
use_default_route = true

# Optional router checks. One successful TCP connect means the LAN is up.
# Prefer an IP literal. A hostname depends on DNS, which is often what just died.
# [[network.lan_probes]]
# host = "192.168.1.1"
# port = 80

[[network.internet_probes]]
host = "1.1.1.1"
port = 443

[[network.internet_probes]]
host = "8.8.8.8"
port = 53

[actions]
# Live outages can run these commands. argv is a list, not a shell string.
# `brownout-buddy simulate` records the outage and does not run commands.
command_timeout_seconds = 30

# Remembered for a future "pause these apps" action. v0.1 does not pause
# processes. When this list is non-empty, a power loss logs a stub result.
pause_processes = []

# Both are stubs in v0.1: the monitor logs that it did not change the OS.
dim_brightness = false
battery_saver = false

# Stub in v0.1: the message, including a battery estimate when one exists,
# is written to the log. Native notifications are on the roadmap.
notify = true

# [[actions.commands]]
# on = "power_loss"
# argv = ["echo", "power lost"]
#
# `on` is one of: power_loss, power_restore, internet_down, lan_down,
# connectivity_restore.

[store]
# SQLite file. Empty uses the per-user data directory (see the README).
path = ""

[tray]
# Show a menu-bar / tray icon when a graphical session and the tray
# dependencies are available. Otherwise the monitor runs in the terminal.
enabled = true

[classifier]
# Fuse power, internet, and gateway reachability into a label and a
# confidence score. Light, sentinel, and history signals have interfaces
# but do not affect the score until they are implemented.
enabled = true
# At or below this confidence, a future tray prompt would ask
# "Brownout or unplugged?". v0.1 only records that the question is pending.
prompt_below = 0.6
# A label other than "unknown" needs a winning score at least this high...
min_score = 0.55
# ...and this far ahead of the runner-up.
min_margin = 0.15

[classifier.light]
# Look for a real ambient-light sensor. v0.1 does not read lux.
# The webcam is never used.
enabled = true

[classifier.sentinel]
# Optional always-on LAN device (smart plug or a phone on a charger).
# v0.1 stores the host and does not contact it.
enabled = false
host = ""
port = 9
"""


def load_config(path: Path | None) -> Config:
    """Load ``path``, or the built-in defaults when ``path`` is None.

    A path that does not exist is an error. The CLI treats "no config file
    chosen" as defaults; it does not call this with a missing default path.
    """

    if path is None:
        return Config()
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Could not read config file {path}: {exc}") from exc
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Config file must be a TOML table: {path}")
    return replace(_from_table(data), config_path=path)


def _from_table(data: dict) -> Config:
    _reject_unknown(data, _ROOT_KEYS, "config")
    defaults = Config()
    power = _table(data.get("power"), "power")
    network = _table(data.get("network"), "network")
    actions = _table(data.get("actions"), "actions")
    store = _table(data.get("store"), "store")
    tray = _table(data.get("tray"), "tray")
    classifier = _table(data.get("classifier"), "classifier")
    light = _table(classifier.get("light"), "classifier.light")
    sentinel = _table(classifier.get("sentinel"), "classifier.sentinel")
    _reject_unknown(power, {"enabled"}, "power")
    _reject_unknown(
        network,
        {
            "enabled",
            "timeout_seconds",
            "failure_threshold",
            "recovery_threshold",
            "use_default_route",
            "lan_probes",
            "internet_probes",
        },
        "network",
    )
    _reject_unknown(
        actions,
        {
            "command_timeout_seconds",
            "pause_processes",
            "dim_brightness",
            "battery_saver",
            "notify",
            "commands",
        },
        "actions",
    )
    _reject_unknown(store, {"path"}, "store")
    _reject_unknown(tray, {"enabled"}, "tray")
    _reject_unknown(
        classifier,
        {"enabled", "prompt_below", "min_score", "min_margin", "light", "sentinel"},
        "classifier",
    )
    _reject_unknown(light, {"enabled"}, "classifier.light")
    _reject_unknown(
        sentinel, {"enabled", "host", "port"}, "classifier.sentinel"
    )

    internet = (
        defaults.internet_probes
        if "internet_probes" not in network
        else _probes(network["internet_probes"], "network.internet_probes")
    )
    lan = (
        defaults.lan_probes
        if "lan_probes" not in network
        else _probes(network["lan_probes"], "network.lan_probes")
    )
    network_enabled = _bool(network.get("enabled"), "network.enabled", True)
    if network_enabled and not internet:
        raise ConfigError(
            "network.internet_probes must list at least one host while network "
            "monitoring is enabled."
        )

    return Config(
        poll_interval_seconds=_positive_number(
            data.get("poll_interval_seconds"),
            "poll_interval_seconds",
            defaults.poll_interval_seconds,
        ),
        timezone=_timezone(data.get("timezone"), defaults.timezone),
        power_enabled=_bool(power.get("enabled"), "power.enabled", True),
        network_enabled=network_enabled,
        network_timeout_seconds=_positive_number(
            network.get("timeout_seconds"),
            "network.timeout_seconds",
            defaults.network_timeout_seconds,
        ),
        failure_threshold=_positive_int(
            network.get("failure_threshold"),
            "network.failure_threshold",
            defaults.failure_threshold,
        ),
        recovery_threshold=_positive_int(
            network.get("recovery_threshold"),
            "network.recovery_threshold",
            defaults.recovery_threshold,
        ),
        use_default_route=_bool(
            network.get("use_default_route"),
            "network.use_default_route",
            True,
        ),
        lan_probes=lan,
        internet_probes=internet,
        command_timeout_seconds=_positive_number(
            actions.get("command_timeout_seconds"),
            "actions.command_timeout_seconds",
            defaults.command_timeout_seconds,
        ),
        pause_processes=_string_list(
            actions.get("pause_processes"), "actions.pause_processes"
        ),
        dim_brightness=_bool(
            actions.get("dim_brightness"), "actions.dim_brightness", False
        ),
        battery_saver=_bool(
            actions.get("battery_saver"), "actions.battery_saver", False
        ),
        notify=_bool(actions.get("notify"), "actions.notify", True),
        commands=_commands(actions.get("commands")),
        store_path=_string(store.get("path"), "store.path", ""),
        tray_enabled=_bool(tray.get("enabled"), "tray.enabled", True),
        classifier_enabled=_bool(
            classifier.get("enabled"), "classifier.enabled", True
        ),
        classifier_prompt_below=_unit_interval(
            classifier.get("prompt_below"),
            "classifier.prompt_below",
            defaults.classifier_prompt_below,
        ),
        classifier_min_score=_unit_interval(
            classifier.get("min_score"),
            "classifier.min_score",
            defaults.classifier_min_score,
        ),
        classifier_min_margin=_unit_interval(
            classifier.get("min_margin"),
            "classifier.min_margin",
            defaults.classifier_min_margin,
        ),
        light_enabled=_bool(light.get("enabled"), "classifier.light.enabled", True),
        sentinel_enabled=_bool(
            sentinel.get("enabled"), "classifier.sentinel.enabled", False
        ),
        sentinel_host=_string(
            sentinel.get("host"), "classifier.sentinel.host", ""
        ),
        sentinel_port=_port(
            sentinel.get("port"), "classifier.sentinel.port", defaults.sentinel_port
        ),
    )


_ROOT_KEYS = {
    "poll_interval_seconds",
    "timezone",
    "power",
    "network",
    "actions",
    "store",
    "tray",
    "classifier",
}


def _table(value: object, name: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be a table.")
    return value


def _reject_unknown(data: dict, allowed: set[str], where: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        joined = ", ".join(unknown)
        raise ConfigError(f"Unknown {where} key: {joined}.")


def _bool(value: object, name: str, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ConfigError(f"{name} must be true or false.")
    return value


def _timezone(value: object, default: str) -> str:
    text = _string(value, "timezone", default)
    if text == "":
        return ""
    from zoneinfo import ZoneInfo
    from zoneinfo import ZoneInfoNotFoundError

    try:
        ZoneInfo(text)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(
            f"Unknown timezone {text!r}. Use an IANA name such as 'Asia/Manila', "
            "or leave timezone empty to use this computer's local zone."
        ) from exc
    return text


def _string(value: object, name: str, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ConfigError(f"{name} must be a string.")
    return value


def _unit_interval(value: object, name: str, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a number from 0 to 1.")
    number = float(value)
    if not 0 <= number <= 1:
        raise ConfigError(f"{name} must be from 0 to 1.")
    return number


def _port(value: object, name: str, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ConfigError(f"{name} must be an integer from 1 to 65535.")
    return value


def _positive_number(value: object, name: str, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a number greater than 0.")
    if value <= 0:
        raise ConfigError(f"{name} must be greater than 0.")
    return float(value)


def _positive_int(value: object, name: str, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be an integer greater than 0.")
    if value <= 0:
        raise ConfigError(f"{name} must be greater than 0.")
    return value


def _string_list(value: object, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{name} must be a list of strings.")
    return tuple(value)


def _probes(value: object, name: str) -> tuple[ProbeConfig, ...]:
    if not isinstance(value, list):
        raise ConfigError(f"{name} must be a list of tables with host and port.")
    probes: list[ProbeConfig] = []
    for index, item in enumerate(value):
        label = f"{name}[{index}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{label} must be a table with host and port.")
        _reject_unknown(item, {"host", "port"}, label)
        host = item.get("host")
        port = item.get("port")
        if not isinstance(host, str) or not host.strip():
            raise ConfigError(f"{label}.host must be a non-empty string.")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ConfigError(f"{label}.port must be an integer from 1 to 65535.")
        probes.append(ProbeConfig(host.strip(), port))
    return tuple(probes)


def _commands(value: object) -> tuple[CommandConfig, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ConfigError("actions.commands must be a list of tables.")
    commands: list[CommandConfig] = []
    for index, item in enumerate(value):
        label = f"actions.commands[{index}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{label} must be a table with on and argv.")
        _reject_unknown(item, {"on", "argv"}, label)
        event = item.get("on")
        argv = item.get("argv")
        if not isinstance(event, str) or event not in VALID_COMMAND_EVENTS:
            allowed = ", ".join(sorted(VALID_COMMAND_EVENTS))
            raise ConfigError(f"{label}.on must be one of: {allowed}.")
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(part, str) and part for part in argv)
        ):
            raise ConfigError(f"{label}.argv must be a non-empty list of strings.")
        commands.append(CommandConfig(event, tuple(argv)))
    return tuple(commands)
