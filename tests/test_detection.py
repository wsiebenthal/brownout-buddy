from pathlib import Path

import pytest

from brownout_buddy.config import Config, ProbeConfig
from brownout_buddy.detection.network import (
    classify_network,
    parse_proc_net_route,
    probe_network,
    read_default_route,
)
from brownout_buddy.detection.power import interpret_battery, read_power
from brownout_buddy.models import NetworkStatus, PowerSource, RouteInfo


def test_interpret_battery_maps_plugged_state_and_sentinels():
    ac = interpret_battery(True, percent=88, secsleft=120)
    assert ac.source is PowerSource.AC
    assert ac.percent == 88
    assert ac.seconds_left == 120

    battery = interpret_battery(False, percent=10, secsleft=-1)
    assert battery.source is PowerSource.BATTERY
    assert battery.seconds_left is None

    unknown = interpret_battery(None, secsleft=-2)
    assert unknown.source is PowerSource.UNKNOWN
    assert unknown.seconds_left is None


def test_read_power_does_not_raise_without_a_battery():
    reading = read_power()
    assert reading.source in {PowerSource.AC, PowerSource.BATTERY, PowerSource.UNKNOWN}


@pytest.mark.parametrize(
    ("internet_up", "lan", "route", "expected"),
    [
        (True, None, None, NetworkStatus.ONLINE),
        (True, False, False, NetworkStatus.ONLINE),
        (False, True, None, NetworkStatus.INTERNET_DOWN),
        (False, False, True, NetworkStatus.LAN_DOWN),
        (False, None, False, NetworkStatus.LAN_DOWN),
        (False, None, True, NetworkStatus.INTERNET_DOWN),
        (False, None, None, NetworkStatus.INTERNET_DOWN),
    ],
)
def test_classify_network(internet_up, lan, route, expected):
    assert (
        classify_network(
            internet_up=internet_up,
            lan_probe_up=lan,
            has_default_route=route,
        )
        is expected
    )


def test_parse_proc_net_route_reads_default_gateway():
    text = (
        "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n"
        "eth0 00000000 0101A8C0 0003 0 0 0 00000000 0 0 0\n"
    )
    info = parse_proc_net_route(text)
    assert info.checked is True
    assert info.has_default_route is True
    assert info.gateway == "192.168.1.1"


def test_parse_proc_net_route_without_default():
    text = (
        "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n"
        "eth0 0000A8C0 0101A8C0 0003 0 0 0 00FFFFFF 0 0 0\n"
    )
    info = parse_proc_net_route(text)
    assert info.has_default_route is False
    assert info.gateway is None


def test_probe_network_uses_injected_probe_and_route(tmp_path: Path):
    config = Config(
        internet_probes=(ProbeConfig("203.0.113.1", 443),),
        lan_probes=(ProbeConfig("192.0.2.1", 80),),
        network_timeout_seconds=0.1,
    )
    calls = []

    def probe(host, port, timeout):
        calls.append((host, port, timeout))
        return host == "192.0.2.1"

    reading = probe_network(
        config,
        probe=probe,
        route_lookup=lambda: RouteInfo(False, None, None, "test"),
    )
    assert reading.status is NetworkStatus.INTERNET_DOWN
    assert calls == [("203.0.113.1", 443, 0.1), ("192.0.2.1", 80, 0.1)]
    assert "LAN probes" in reading.note


def test_linux_route_reader_reports_unreadable(tmp_path: Path):
    missing = tmp_path / "no-such-route"
    info = read_default_route(proc_path=missing)
    assert info.checked is False
    assert info.method == "unreadable"
