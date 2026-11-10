import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from brownout_buddy.classifier.engine import OutageClassifier, default_classifier
from brownout_buddy.classifier.light import detect_light
from brownout_buddy.classifier.ping import icmp_ping, ping_command
from brownout_buddy.classifier.prompt import StubConfirmationPrompt
from brownout_buddy.classifier.score import UPS_CAVEAT, score_readings
from brownout_buddy.classifier.signals import (
    GatewaySignal,
    InternetCoincidenceSignal,
    LightSensorSignal,
    PatternSignal,
    SentinelSignal,
)
from brownout_buddy.classifier.types import ClassifyContext, SignalReading
from brownout_buddy.config import Config
from brownout_buddy.models import NetworkStatus, OutageLabel, PowerSource

NOW = datetime(2026, 5, 1, tzinfo=timezone.utc)


def _ctx(**overrides) -> ClassifyContext:
    base = dict(
        previous_power=PowerSource.AC,
        power=PowerSource.BATTERY,
        previous_network=NetworkStatus.ONLINE,
        network=NetworkStatus.ONLINE,
    )
    base.update(overrides)
    return ClassifyContext(**base)


def _reading(name: str, state: str, *, stub: bool = False) -> SignalReading:
    return SignalReading(name=name, state=state, stub=stub, detail="", source="test")


def _score(*readings: SignalReading):
    return score_readings(readings)


def test_unplug_is_high_confidence_when_gateway_and_internet_stay_up():
    result = _score(
        _reading("internet_coincidence", "still_up"),
        _reading("gateway", "up"),
    )
    assert result.label is OutageLabel.UNPLUGGED
    assert result.confidence == pytest.approx(0.80)
    assert result.prompt is False
    assert any(UPS_CAVEAT in note for note in result.notes)


def test_router_down_with_light_drop_is_a_brownout():
    result = _score(
        _reading("internet_coincidence", "coinciding"),
        _reading("gateway", "down"),
        _reading("ambient_light", "dropped"),
    )
    assert result.label is OutageLabel.BROWNOUT
    assert result.confidence == pytest.approx(0.95)
    assert result.prompt is False


def test_router_down_without_light_is_a_brownout_below_the_cap():
    result = _score(
        _reading("internet_coincidence", "coinciding"),
        _reading("gateway", "down"),
    )
    assert result.label is OutageLabel.BROWNOUT
    assert result.confidence == pytest.approx(0.75)


def test_silent_sentinel_raises_brownout_confidence_when_injected():
    without = _score(
        _reading("internet_coincidence", "coinciding"),
        _reading("gateway", "down"),
        _reading("sentinel", "unavailable", stub=True),
    )
    with_silent = _score(
        _reading("internet_coincidence", "coinciding"),
        _reading("gateway", "down"),
        _reading("sentinel", "silent"),
    )
    assert without.confidence == pytest.approx(0.75)
    assert with_silent.confidence == pytest.approx(0.95)


def test_stub_light_drop_does_not_change_the_score():
    plain = _score(
        _reading("internet_coincidence", "coinciding"),
        _reading("gateway", "down"),
    )
    stubbed = _score(
        _reading("internet_coincidence", "coinciding"),
        _reading("gateway", "down"),
        _reading("ambient_light", "dropped", stub=True),
    )
    assert stubbed.label is plain.label
    assert stubbed.confidence == pytest.approx(plain.confidence)


def test_ac_loss_without_gateway_stays_unknown_and_asks():
    result = _score(_reading("internet_coincidence", "still_up"))
    assert result.label is OutageLabel.UNKNOWN
    assert result.leading is OutageLabel.UNPLUGGED
    assert result.confidence == pytest.approx(0.35)
    assert result.prompt is True
    assert result.question == "Brownout or unplugged?"


def test_isp_outage_when_mains_stay_up_and_gateway_answers():
    result = _score(
        _reading("internet_coincidence", "internet_only"),
        _reading("gateway", "up"),
    )
    assert result.label is OutageLabel.ISP_OUTAGE
    assert result.confidence == pytest.approx(0.70)
    assert result.prompt is False


def test_gateway_down_on_mains_is_not_an_isp_outage_and_does_not_ask():
    result = _score(
        _reading("internet_coincidence", "internet_only"),
        _reading("gateway", "down"),
    )
    assert result.label is OutageLabel.UNKNOWN
    assert result.prompt is False
    assert result.confidence == pytest.approx(0.0)


def test_unknown_signal_name_is_ignored():
    base = _score(
        _reading("internet_coincidence", "still_up"),
        _reading("gateway", "up"),
    )
    extra = _score(
        _reading("internet_coincidence", "still_up"),
        _reading("gateway", "up"),
        _reading("weather", "storm"),
    )
    assert extra.label is base.label
    assert extra.confidence == pytest.approx(base.confidence)


def test_default_signals_match_the_two_live_signals_for_an_unplug():
    ctx = _ctx(gateway_reachable=True, history=("ignored",))
    full = default_classifier(Config()).classify(ctx)
    short = OutageClassifier(
        [InternetCoincidenceSignal(), GatewaySignal(pinger=lambda *_: True)]
    ).classify(ctx)
    assert full is not None and short is not None
    assert full.label is short.label is OutageLabel.UNPLUGGED
    assert full.confidence == pytest.approx(short.confidence)
    names = [reading.name for reading in full.readings]
    assert names == [
        "internet_coincidence",
        "gateway",
        "ambient_light",
        "sentinel",
        "pattern",
    ]
    assert full.readings[2].stub is True
    assert full.readings[3].stub is True
    assert full.readings[4].stub is True


def test_pattern_history_does_not_change_the_label():
    signal = PatternSignal()
    empty = signal.read(_ctx(history=()))
    filled = signal.read(_ctx(history=("row", "row")))
    assert empty == filled
    assert empty.stub is True


def test_gateway_signal_does_not_ping_when_the_simulator_overrides():
    def boom(host, timeout):
        raise AssertionError(f"pinged {host} after {timeout}")

    reading = GatewaySignal(pinger=boom).read(_ctx(gateway_reachable=False))
    assert reading.state == "down"
    assert reading.stub is False


def test_gateway_ping_failure_to_run_is_unknown_not_down():
    reading = GatewaySignal(pinger=lambda host, timeout: None).read(
        _ctx(
            gateway_reachable=None,
            probe_gateway=True,
            gateway_host="192.0.2.1",
        )
    )
    assert reading.state == "unknown"
    assert "not marked down" in reading.detail


def test_ping_command_is_a_single_argv_per_platform():
    assert ping_command("192.0.2.1", 1.5, "linux") == [
        "ping",
        "-c",
        "1",
        "-W",
        "1",
        "192.0.2.1",
    ]
    assert ping_command("192.0.2.1", 1.5, "darwin")[1:4] == ["-c", "1", "-W"]
    assert ping_command("192.0.2.1", 1.5, "win32")[:3] == ["ping", "-n", "1"]
    assert icmp_ping("-n", 1) is None


def test_light_capability_degrades_without_using_a_camera(tmp_path: Path):
    source = (
        Path(__file__).resolve().parents[1] / "src" / "brownout_buddy" / "classifier" / "light.py"
    ).read_text(encoding="utf-8")
    assert "webcam" in source.lower()
    assert "/dev/video" not in source
    assert "ImageCapture" not in source

    empty = detect_light(platform="linux", sysfs_root=tmp_path)
    assert empty.present is False
    assert empty.supported is True

    mac = detect_light(platform="darwin")
    assert mac.supported is False
    assert "undocumented" in mac.detail
    windows = detect_light(platform="win32")
    assert "LightSensor" in windows.detail
    assert windows.supported is False


@pytest.mark.skipif(
    sys.platform == "win32", reason="sysfs IIO names contain a colon, invalid on Windows"
)
def test_light_capability_detects_sysfs_illuminance_sensor(tmp_path: Path):
    device = tmp_path / "iio:device0"
    device.mkdir()
    (device / "in_illuminance_raw").write_text("10\n", encoding="utf-8")
    found = detect_light(platform="linux", sysfs_root=tmp_path)
    assert found.present is True
    assert "iio:device0" in found.detail


def test_live_light_signal_is_a_stub_until_injected():
    live = LightSensorSignal(detect=lambda: detect_light(platform="darwin")).read(_ctx())
    assert live.stub is True
    injected = LightSensorSignal().read(_ctx(light="drop"))
    assert injected.stub is False
    assert injected.state == "dropped"


def test_configured_sentinel_is_not_contacted():
    reading = SentinelSignal(enabled=True, host="192.0.2.50").read(_ctx())
    assert reading.stub is True
    assert "not contacted" in reading.detail
    injected = SentinelSignal().read(_ctx(sentinel="silent"))
    assert injected.state == "silent"
    assert injected.stub is False


def test_prompt_stub_returns_no_answer():
    classification = _score(_reading("internet_coincidence", "still_up"))
    assert StubConfirmationPrompt().ask(classification, [1]) is None
    text = StubConfirmationPrompt.menu_text(classification, [4])
    assert "Brownout or unplugged?" in text
    assert "brownout-buddy label 4" in text
