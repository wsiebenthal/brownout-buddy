from datetime import datetime, timedelta, timezone

import pytest

from brownout_buddy.models import NetworkStatus, OutageType, PowerSource
from brownout_buddy.tracking import Debouncer, Tracker

T0 = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _tracker():
    tracker = Tracker()
    tracker.seed(PowerSource.AC, NetworkStatus.ONLINE)
    return tracker


def test_baseline_seed_opens_nothing():
    tracker = Tracker()
    assert tracker.apply(PowerSource.BATTERY, NetworkStatus.ONLINE, T0) == []
    assert tracker.power is PowerSource.BATTERY
    assert tracker.open_outages == {}


def test_ac_to_battery_opens_and_restore_closes_with_duration():
    tracker = _tracker()
    started = tracker.apply(PowerSource.BATTERY, NetworkStatus.ONLINE, T0)
    assert [event.type for event in started] == [OutageType.POWER]
    ended = tracker.apply(
        PowerSource.AC, NetworkStatus.ONLINE, T0 + timedelta(seconds=125)
    )
    assert len(ended) == 1
    assert ended[0].type is OutageType.POWER
    assert ended[0].duration_seconds == 125
    assert tracker.open_outages == {}


def test_second_power_loss_does_not_duplicate():
    tracker = _tracker()
    tracker.apply(PowerSource.BATTERY, NetworkStatus.ONLINE, T0)
    assert tracker.apply(PowerSource.BATTERY, NetworkStatus.ONLINE, T0) == []


def test_unknown_power_does_not_open_or_close():
    tracker = _tracker()
    tracker.apply(PowerSource.BATTERY, NetworkStatus.ONLINE, T0)
    assert tracker.apply(PowerSource.UNKNOWN, NetworkStatus.ONLINE, T0) == []
    assert OutageType.POWER in tracker.open_outages
    assert tracker.power is PowerSource.BATTERY


def test_internet_and_lan_are_separate_rows():
    tracker = _tracker()
    internet = tracker.apply(PowerSource.AC, NetworkStatus.INTERNET_DOWN, T0)
    assert [event.type for event in internet] == [OutageType.INTERNET]
    switched = tracker.apply(
        PowerSource.AC, NetworkStatus.LAN_DOWN, T0 + timedelta(seconds=5)
    )
    assert [event.type for event in switched] == [OutageType.INTERNET, OutageType.LAN]
    assert switched[0].duration_seconds == 5
    assert OutageType.LAN in tracker.open_outages
    assert OutageType.INTERNET not in tracker.open_outages


def test_power_and_network_outages_overlap():
    tracker = _tracker()
    events = tracker.apply(PowerSource.BATTERY, NetworkStatus.LAN_DOWN, T0)
    assert {event.type for event in events} == {OutageType.POWER, OutageType.LAN}


def test_naive_timestamp_is_rejected():
    tracker = _tracker()
    with pytest.raises(ValueError):
        tracker.apply(PowerSource.BATTERY, NetworkStatus.ONLINE, datetime(2026, 5, 1))


def test_debouncer_waits_for_repeated_failures_and_recovers_faster():
    debouncer = Debouncer(failure_threshold=2, recovery_threshold=1)
    assert debouncer.push(NetworkStatus.ONLINE) is NetworkStatus.ONLINE
    assert debouncer.push(NetworkStatus.INTERNET_DOWN) is NetworkStatus.ONLINE
    assert debouncer.push(NetworkStatus.INTERNET_DOWN) is NetworkStatus.INTERNET_DOWN
    assert debouncer.push(NetworkStatus.UNKNOWN) is NetworkStatus.INTERNET_DOWN
    assert debouncer.push(NetworkStatus.ONLINE) is NetworkStatus.ONLINE
