from datetime import datetime, timedelta, timezone
from pathlib import Path

from brownout_buddy.cli import main
from brownout_buddy.models import NetworkReading, NetworkStatus, PowerReading, PowerSource


def test_simulator_cli_labels_and_exports(tmp_path: Path, capsys, monkeypatch):
    clock = {"now": datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)}

    def now():
        return clock["now"]

    monkeypatch.setattr("brownout_buddy.cli.current_time", now)
    db = tmp_path / "outages.sqlite"
    base = ["--db", str(db)]

    assert main(base + ["simulate", "power-loss", "--router-down", "--light-drop"]) == 0
    brownout = capsys.readouterr().out
    assert "classifier: brownout (confidence 0.95)" in brownout
    assert "ambient_light=dropped" in brownout
    assert "pattern=unavailable stub" in brownout

    clock["now"] += timedelta(minutes=5)
    assert main(base + ["simulate", "restore"]) == 0
    assert "after 5m 0s" in capsys.readouterr().out

    assert main(base + ["simulate", "unplug"]) == 0
    unplug = capsys.readouterr().out
    assert "classifier: unplugged (confidence 0.80)" in unplug
    assert "router on a UPS" in unplug

    assert main(base + ["simulate", "offline"]) == 0
    capsys.readouterr()
    assert main(base + ["history"]) == 0
    history = capsys.readouterr().out
    assert "label=brownout" in history
    assert "label=unplugged" in history
    assert "label=isp-outage" in history

    assert main(base + ["stats"]) == 0
    stats = capsys.readouterr().out
    assert "By day" in stats
    assert "Charts are not implemented" in stats

    csv_path = tmp_path / "outages.csv"
    assert main(base + ["export", str(csv_path)]) == 0
    text = csv_path.read_text(encoding="utf-8")
    assert "ground_truth" in text
    assert "brownout" in text

    assert main(base + ["label", "1", "brownout"]) == 0
    labeled = capsys.readouterr().out
    assert "ground truth set to brownout" in labeled
    assert "remains brownout" in labeled

    assert main(base + ["status", "--json"]) == 0
    assert '"tray"' in capsys.readouterr().out

    assert main(base + ["simulate", "power-loss", "--router-down", "--router-up"]) == 2


def test_stats_since_filters_and_rejects_a_bad_date(tmp_path: Path, capsys, monkeypatch):
    clock = {"now": datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)}
    monkeypatch.setattr("brownout_buddy.cli.current_time", lambda: clock["now"])
    config = tmp_path / "utc.toml"
    config.write_text('timezone = "UTC"\n', encoding="utf-8")
    base = ["--config", str(config), "--db", str(tmp_path / "outages.sqlite")]
    assert main(base + ["simulate", "unplug"]) == 0
    capsys.readouterr()
    clock["now"] = datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc)
    assert main(base + ["simulate", "offline"]) == 0
    capsys.readouterr()

    assert main(base + ["stats", "--by", "day", "--since", "2026-05-03"]) == 0
    kept = capsys.readouterr().out
    assert "since 2026-05-03" in kept
    assert "internet:" in kept
    assert "power:" not in kept
    assert main(base + ["stats", "--since", "not-a-date"]) == 2


def test_low_confidence_prompt_text(tmp_path: Path, capsys):
    db = tmp_path / "outages.sqlite"
    assert main(["--db", str(db), "simulate", "power-loss"]) == 0
    text = capsys.readouterr().out
    assert "classifier: unknown" in text
    assert "leading guess unplugged" in text
    assert "prompt: stub:" in text
    assert "Brownout or unplugged?" in text


def test_init_config_and_headless_baseline(tmp_path: Path, capsys, monkeypatch):
    destination = tmp_path / "nested" / "config.toml"
    assert main(["init-config", "--path", str(destination)]) == 0
    assert destination.is_file()
    assert "webcam is never used" in destination.read_text(encoding="utf-8")
    assert main(["init-config", "--path", str(destination)]) == 2

    monkeypatch.setattr(
        "brownout_buddy.monitor.read_power",
        lambda: PowerReading(PowerSource.AC, method="fake"),
    )
    monkeypatch.setattr(
        "brownout_buddy.monitor.read_network",
        lambda _config: NetworkReading(status=NetworkStatus.ONLINE, note="fake probe"),
    )
    db = tmp_path / "live.sqlite"
    assert main(["--db", str(db), "run", "--once", "--headless"]) == 0
    output = capsys.readouterr().out
    assert "Recorded a baseline" in output
    assert "tray: normal" in output
