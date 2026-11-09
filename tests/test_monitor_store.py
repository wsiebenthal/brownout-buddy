import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from brownout_buddy.classifier.engine import default_classifier
from brownout_buddy.config import Config
from brownout_buddy.models import (
    NetworkReading,
    NetworkStatus,
    OutageLabel,
    OutageType,
    PowerReading,
    PowerSource,
    RouteInfo,
)
from brownout_buddy.monitor import Monitor
from brownout_buddy.store import OutageStore, StoreError

T0 = datetime(2026, 1, 1, 16, 30, tzinfo=timezone.utc)


def _monitor(tmp_path: Path, **config_overrides) -> Monitor:
    config = Config(**config_overrides) if config_overrides else Config()
    # Config is frozen and the test passes field overrides.
    return Monitor(config, OutageStore(tmp_path / "outages.sqlite"))


def test_simulate_unplug_and_brownout_round_trip(tmp_path: Path):
    monitor = _monitor(tmp_path)
    unplug = monitor.simulate("unplug", T0, battery_percent=40, battery_minutes=30)
    assert unplug.classification is not None
    assert unplug.classification.label is OutageLabel.UNPLUGGED
    assert unplug.classification.confidence == pytest.approx(0.80)
    power = next(event for event in unplug.events if event.type is OutageType.POWER)
    stored = monitor.store.get(power.outage.id)
    assert stored is not None
    assert stored.label == "unplugged"
    assert stored.confidence == pytest.approx(0.80)
    assert stored.detail["battery_percent"] == 40
    assert stored.ground_truth is None

    monitor.simulate("restore", T0 + timedelta(minutes=1))
    brownout = monitor.simulate(
        "power-loss",
        T0 + timedelta(minutes=2),
        router_down=True,
        light_drop=True,
    )
    assert brownout.classification is not None
    assert brownout.classification.label is OutageLabel.BROWNOUT
    assert brownout.classification.confidence == pytest.approx(0.95)
    kinds = {event.type for event in brownout.events}
    assert OutageType.POWER in kinds
    assert OutageType.LAN in kinds
    for event in brownout.events:
        if event.type is OutageType.POWER or event.type is OutageType.LAN:
            row = monitor.store.get(event.outage.id)
            assert row is not None
            assert row.label == "brownout"
            assert row.source == "simulated"


def test_bare_power_loss_asks_and_label_command_keeps_the_model(tmp_path: Path):
    monitor = _monitor(tmp_path)
    result = monitor.simulate("power-loss", T0)
    assert result.classification is not None
    assert result.classification.label is OutageLabel.UNKNOWN
    assert result.classification.prompt is True
    outage_id = result.events[0].outage.id
    updated = monitor.store.set_ground_truth(outage_id, "unplugged")
    assert updated.ground_truth == "unplugged"
    assert updated.label == "unknown"
    assert updated.signals["prompt"] is False
    with pytest.raises(StoreError):
        monitor.store.set_ground_truth(outage_id, "maybe")
    with pytest.raises(StoreError):
        monitor.store.set_ground_truth(999, "brownout")


def test_offline_is_an_isp_outage_and_restore_records_duration(tmp_path: Path):
    monitor = _monitor(tmp_path)
    opened = monitor.simulate("offline", T0)
    assert opened.classification is not None
    assert opened.classification.label is OutageLabel.ISP_OUTAGE
    closed = monitor.simulate("restore", T0 + timedelta(seconds=90))
    assert closed.events[0].duration_seconds == 90
    history = monitor.store.recent(limit=5)
    assert history[0].duration_seconds == 90
    assert history[0].type is OutageType.INTERNET


def test_simulator_does_not_ping(tmp_path: Path):
    def boom(host, timeout):
        raise AssertionError(f"pinged {host}")

    config = Config()
    monitor = Monitor(
        config,
        OutageStore(tmp_path / "outages.sqlite"),
        classifier=default_classifier(config, pinger=boom),
    )
    monitor.simulate("power-loss", T0, router_down=True)
    monitor.simulate("offline", T0 + timedelta(seconds=5))


def test_live_poll_pings_gateway_and_classifies(tmp_path: Path):
    pings = []

    def pinger(host, timeout):
        pings.append((host, timeout))
        return False

    samples = [
        (
            PowerReading(PowerSource.AC, percent=100, seconds_left=None, method="fake"),
            NetworkReading(
                status=NetworkStatus.ONLINE,
                route=RouteInfo(True, True, "192.0.2.1", "test"),
            ),
        ),
        (
            PowerReading(PowerSource.BATTERY, percent=80, seconds_left=600, method="fake"),
            NetworkReading(
                status=NetworkStatus.LAN_DOWN,
                route=RouteInfo(True, True, "192.0.2.1", "test"),
            ),
        ),
    ]

    def power_reader():
        return samples[0][0] if not power_reader.calls else samples[1][0]

    def network_reader():
        power_reader.calls += 1
        return samples[0][1] if power_reader.calls == 1 else samples[1][1]

    power_reader.calls = 0
    config = Config(failure_threshold=1, recovery_threshold=1)
    monitor = Monitor(
        config,
        OutageStore(tmp_path / "outages.sqlite"),
        power_reader=power_reader,
        network_reader=network_reader,
        classifier=default_classifier(config, pinger=pinger),
    )
    baseline = monitor.poll()
    assert baseline.baseline is True
    assert pings == []
    result = monitor.poll()
    assert pings and pings[0][0] == "192.0.2.1"
    assert result.classification is not None
    assert result.classification.label is OutageLabel.BROWNOUT
    assert result.classification.confidence == pytest.approx(0.75)
    assert any(action.name == "notify" and action.status == "stub" for action in result.actions)


def test_pause_skips_live_samples(tmp_path: Path):
    monitor = _monitor(tmp_path)
    monitor.set_paused(True, T0)
    calls = []
    monitor.power_reader = lambda: calls.append("power") or PowerReading(PowerSource.BATTERY)
    monitor.network_reader = lambda: calls.append("net") or NetworkReading(NetworkStatus.LAN_DOWN)
    result = monitor.poll()
    assert result.paused is True
    assert calls == []
    assert monitor.store.recent() == []


def test_restart_keeps_an_open_outage(tmp_path: Path):
    path = tmp_path / "outages.sqlite"
    first = Monitor(Config(), OutageStore(path))
    first.simulate("unplug", T0)
    first.store.close()
    second = Monitor(Config(), OutageStore(path))
    assert second.tracker.seeded is True
    assert second.tracker.power is PowerSource.BATTERY
    again = second.simulate("unplug", T0 + timedelta(seconds=10))
    assert again.events == []


def test_stats_use_the_configured_zone_and_csv_round_trips(tmp_path: Path):
    monitor = _monitor(tmp_path)
    monitor.simulate("unplug", T0)
    monitor.simulate("restore", T0 + timedelta(seconds=90))
    zone = ZoneInfo("Asia/Manila")
    day = monitor.store.stats(by="day", tz=zone, now=T0 + timedelta(seconds=90))
    week = monitor.store.stats(by="week", tz=zone, now=T0 + timedelta(seconds=90))
    assert [(bucket.period, bucket.type, bucket.duration_seconds) for bucket in day] == [
        ("2026-01-02", OutageType.POWER, 90)
    ]
    assert week[0].period == "2026-W01"
    destination = tmp_path / "out.csv"
    assert monitor.store.export_csv(destination) == 1
    with destination.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["type"] == "power"
    assert rows[0]["label"] == "unplugged"
    assert rows[0]["duration_seconds"] == "90"
    assert rows[0]["open"] == "false"


def test_classifier_can_be_disabled(tmp_path: Path):
    monitor = _monitor(tmp_path, classifier_enabled=False)
    result = monitor.simulate("unplug", T0)
    assert result.classification is None
    assert monitor.store.recent()[0].label is None
