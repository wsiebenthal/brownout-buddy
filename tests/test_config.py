from dataclasses import fields
from pathlib import Path

import pytest

from brownout_buddy.config import EXAMPLE_TOML, Config, ConfigError, load_config

ROOT = Path(__file__).resolve().parents[1]


def test_example_file_matches_embedded_template():
    example = (ROOT / "config.example.toml").read_text(encoding="utf-8")
    assert example == EXAMPLE_TOML


def test_example_config_matches_builtin_defaults():
    loaded = load_config(ROOT / "config.example.toml")
    defaults = Config()
    for field in fields(Config):
        if field.name == "config_path":
            continue
        assert getattr(loaded, field.name) == getattr(defaults, field.name)


def test_missing_file_is_an_error(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.toml")


def test_unknown_key_and_bad_port(tmp_path: Path):
    bad_key = tmp_path / "key.toml"
    bad_key.write_text('nickname = "laptop"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="Unknown config key"):
        load_config(bad_key)

    bad_port = tmp_path / "port.toml"
    bad_port.write_text(
        """
        [[network.internet_probes]]
        host = "203.0.113.5"
        port = 70000
        """,
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="port"):
        load_config(bad_port)


def test_bad_command_event_and_timezone(tmp_path: Path):
    commands = tmp_path / "commands.toml"
    commands.write_text(
        """
        [[actions.commands]]
        on = "reboot-the-city"
        argv = ["echo", "no"]
        """,
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="actions.commands"):
        load_config(commands)

    zone = tmp_path / "zone.toml"
    zone.write_text('timezone = "Not/AZone"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="timezone"):
        load_config(zone)


def test_classifier_bounds(tmp_path: Path):
    path = tmp_path / "classifier.toml"
    path.write_text(
        """
        [classifier]
        prompt_below = 1.5
        """,
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="prompt_below"):
        load_config(path)
