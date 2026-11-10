"""Command line for Brownout Buddy.

``simulate`` writes through the same state machine and classifier as the
live monitor. It does not require a power cut, a display, or a network.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from datetime import date
from pathlib import Path

from brownout_buddy import __version__
from brownout_buddy.config import EXAMPLE_TOML, ConfigError, load_config
from brownout_buddy.models import OutageLabel, OutageType
from brownout_buddy.monitor import Monitor, current_time
from brownout_buddy.paths import default_config_path, resolve_db_path
from brownout_buddy.present import (
    dumps,
    format_history,
    format_poll,
    format_stats,
    format_status,
    record_dict,
    stats_dict,
    status_dict,
    zone_for,
)
from brownout_buddy.store import OutageStore, StoreError
from brownout_buddy.tray import TrayUnavailable, graphical_session, run_tray

_LOG = logging.getLogger("brownout_buddy")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    try:
        if args.command == "init-config":
            return _init_config(args)
        config = load_config(_resolve_config_path(args.config))
        store = OutageStore(resolve_db_path(config, args.db))
        try:
            monitor = Monitor(config, store, clock=current_time)
            return _dispatch(args, monitor)
        finally:
            store.close()
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (StoreError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0


def _dispatch(args: argparse.Namespace, monitor: Monitor) -> int:
    if args.command == "run":
        return _run(args, monitor)
    if args.command == "status":
        return _status(args, monitor)
    if args.command == "history":
        return _history(args, monitor)
    if args.command == "stats":
        return _stats(args, monitor)
    if args.command == "export":
        count = monitor.store.export_csv(Path(args.path))
        print(f"Wrote {count} outages to {args.path}")
        return 0
    if args.command == "simulate":
        return _simulate(args, monitor)
    if args.command == "label":
        return _label(args, monitor)
    if args.command == "pause":
        monitor.set_paused(True)
        print("Monitoring paused. A running monitor picks this up on its next poll.")
        return 0
    if args.command == "resume":
        monitor.set_paused(False)
        print("Monitoring resumed.")
        return 0
    print(f"unknown command {args.command}", file=sys.stderr)
    return 2


def _run(args: argparse.Namespace, monitor: Monitor) -> int:
    if args.headless and args.tray:
        print("Pass only one of --headless and --tray.", file=sys.stderr)
        return 2
    use_tray = _want_tray(args, monitor)
    if args.tray and not use_tray:
        return 1
    if use_tray and not args.once:
        stop = threading.Event()
        try:
            run_tray(monitor, stop, monitor.config.poll_interval_seconds)
            return 0
        except TrayUnavailable as exc:
            if args.tray:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"{exc} Running headless.", file=sys.stderr)
    return _headless(args, monitor)


def _want_tray(args: argparse.Namespace, monitor: Monitor) -> bool:
    if args.headless or args.once or not monitor.config.tray_enabled:
        return False
    if args.tray:
        if not graphical_session():
            print("No graphical session detected.", file=sys.stderr)
            return False
        return True
    return graphical_session()


def _headless(args: argparse.Namespace, monitor: Monitor) -> int:
    stop = threading.Event()
    while not stop.is_set():
        result = monitor.poll()
        if result.changed or args.once or result.actions:
            print(format_poll(monitor, result))
            for action in result.actions:
                _LOG.info("action %s: %s", action.name, action.message)
        if args.once:
            return 0
        if stop.wait(monitor.config.poll_interval_seconds):
            break
    return 0


def _status(args: argparse.Namespace, monitor: Monitor) -> int:
    now = current_time()
    if args.json:
        print(dumps(status_dict(monitor, now)))
    else:
        print(format_status(monitor, now))
    return 0


def _history(args: argparse.Namespace, monitor: Monitor) -> int:
    now = current_time()
    outage_type = OutageType(args.type) if args.type else None
    label = args.label
    records = monitor.store.recent(
        limit=args.limit, outage_type=outage_type, label=label
    )
    if args.json:
        print(dumps([record_dict(record, now) for record in records]))
    else:
        print(format_history(records, now, monitor.config.timezone))
    return 0


def _stats(args: argparse.Namespace, monitor: Monitor) -> int:
    now = current_time()
    zone = zone_for(monitor.config.timezone)
    since = _parse_since(args.since)
    day = monitor.store.stats(by="day", tz=zone, now=now, since=since)
    week = monitor.store.stats(by="week", tz=zone, now=now, since=since)
    name = monitor.config.timezone or "local"
    if args.json:
        payload = stats_dict(name, day, week)
        if since is not None:
            payload["since"] = since.isoformat()
        print(dumps(payload))
        return 0
    if args.by in (None, "day"):
        print(format_stats(_stats_title("day", name, since), day))
    if args.by in (None, "week"):
        if args.by is None:
            print()
        print(format_stats(_stats_title("week", name, since), week))
    return 0


def _parse_since(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("--since must be YYYY-MM-DD") from exc


def _stats_title(kind: str, timezone_name: str, since: date | None) -> str:
    title = f"By {kind} ({timezone_name})"
    if since is not None:
        title += f" since {since.isoformat()}"
    return title


def _simulate(args: argparse.Namespace, monitor: Monitor) -> int:
    result = monitor.simulate(
        args.scenario,
        at=current_time(),
        router_down=args.router_down,
        router_up=args.router_up,
        light_drop=args.light_drop,
        light_steady=args.light_steady,
        sentinel_silent=args.sentinel_silent,
        sentinel_alive=args.sentinel_alive,
        battery_percent=args.battery_percent,
        battery_minutes=args.battery_minutes,
    )
    if not result.events:
        print("No state change.")
    print(format_poll(monitor, result))
    return 0


def _label(args: argparse.Namespace, monitor: Monitor) -> int:
    record = monitor.store.set_ground_truth(args.id, args.ground_truth)
    print(
        f"Outage #{record.id} ground truth set to {record.ground_truth}. "
        f"Classifier label remains {record.label or 'unset'}."
    )
    return 0


def _init_config(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser() if args.path else default_config_path()
    if path.exists() and not args.force:
        raise ConfigError(f"{path} already exists. Pass --force to replace it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(EXAMPLE_TOML, encoding="utf-8")
    print(f"Wrote {path}")
    return 0


def _resolve_config_path(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("BROWNOUT_BUDDY_CONFIG")
    if env:
        return Path(env).expanduser()
    local = Path("brownout-buddy.toml")
    if local.is_file():
        return local
    default = default_config_path()
    if default.is_file():
        return default
    return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brownout-buddy",
        description=(
            "Notice power and internet outages, keep a local log, and label "
            "a brownout versus an unplugged laptop."
        ),
    )
    parser.add_argument("--config", help="TOML config file. Omit to use defaults.")
    parser.add_argument("--db", help="SQLite file. Overrides store.path.")
    parser.add_argument(
        "--version", action="version", version=f"brownout-buddy {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Poll power and the network until quit.")
    run.add_argument("--headless", action="store_true", help="Do not open a tray icon.")
    run.add_argument("--tray", action="store_true", help="Require a tray icon.")
    run.add_argument("--once", action="store_true", help="Take one sample and exit.")

    status = sub.add_parser("status", help="Show the current snapshot.")
    status.add_argument("--json", action="store_true")

    history = sub.add_parser("history", help="List recent outages.")
    history.add_argument("--limit", type=int, default=20)
    history.add_argument("--type", choices=[item.value for item in OutageType])
    history.add_argument("--label", choices=[item.value for item in OutageLabel])
    history.add_argument("--json", action="store_true")

    stats = sub.add_parser("stats", help="Counts and durations by day and week.")
    stats.add_argument("--by", choices=("day", "week"))
    stats.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="Only outages that started on or after this date, in the stats timezone.",
    )
    stats.add_argument("--json", action="store_true")

    export = sub.add_parser("export", help="Write the log to CSV.")
    export.add_argument("path")

    simulate = sub.add_parser(
        "simulate",
        help="Apply a scripted outage without waiting for a real one.",
    )
    simulate.add_argument(
        "scenario",
        choices=[
            "power-loss",
            "unplug",
            "offline",
            "internet-down",
            "lan-down",
            "restore",
        ],
    )
    simulate.add_argument(
        "--router-down",
        action="store_true",
        help="Gateway does not answer. Implies the LAN is down.",
    )
    simulate.add_argument(
        "--router-up",
        action="store_true",
        help="Gateway answers. Does not by itself prove an unplug if the router has a UPS.",
    )
    simulate.add_argument(
        "--light-drop",
        action="store_true",
        help="Inject an ambient-light drop. Live lux is not read.",
    )
    simulate.add_argument("--light-steady", action="store_true")
    simulate.add_argument(
        "--sentinel-silent",
        action="store_true",
        help="Inject a silent LAN sentinel. The real watcher is a stub.",
    )
    simulate.add_argument("--sentinel-alive", action="store_true")
    simulate.add_argument("--battery-percent", type=float)
    simulate.add_argument("--battery-minutes", type=float)

    label = sub.add_parser(
        "label",
        help="Store a ground-truth answer for one outage.",
    )
    label.add_argument("id", type=int)
    label.add_argument("ground_truth", choices=[item.value for item in OutageLabel])

    sub.add_parser("pause", help="Stop live sampling until resume.")
    sub.add_parser("resume", help="Allow live sampling again.")

    init = sub.add_parser("init-config", help="Write the example config.")
    init.add_argument("--path", help="Destination. Default is the per-user config path.")
    init.add_argument("--force", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
