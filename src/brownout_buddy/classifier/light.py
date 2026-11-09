"""Ambient-light capability check.

v0.1 detects whether a sensor seems to exist and then stops. It does not
read lux, and it does not open a camera. macOS has no documented
ambient-light API that this project can call, so that platform is an
explicit unsupported stub. Windows names ``Windows.Devices.Sensors.LightSensor``
as the future API and does not call it yet. Linux looks for an IIO
illuminance file under sysfs.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_IIO_FILES = ("in_illuminance_raw", "in_illuminance_input")


@dataclass(frozen=True)
class LightCapability:
    supported: bool
    present: bool | None
    method: str
    detail: str


def detect_light(
    *,
    platform: str | None = None,
    sysfs_root: Path | None = None,
) -> LightCapability:
    """Report whether an ambient-light sensor can be seen. Never opens a webcam."""

    system = platform if platform is not None else sys.platform
    if system == "darwin":
        return LightCapability(
            supported=False,
            present=None,
            method="macos-undocumented",
            detail=(
                "macOS ambient light is undocumented for this app, so the "
                "sensor is stubbed. The webcam is not used."
            ),
        )
    if system == "win32":
        return LightCapability(
            supported=False,
            present=None,
            method="windows-lightsensor-stub",
            detail=(
                "Windows.Devices.Sensors.LightSensor is the planned API. "
                "v0.1 does not read it. The webcam is not used."
            ),
        )
    root = sysfs_root if sysfs_root is not None else Path("/sys/bus/iio/devices")
    found = _illuminance_devices(root)
    if found:
        names = ", ".join(found)
        return LightCapability(
            supported=True,
            present=True,
            method="linux-iio",
            detail=(
                f"Linux IIO illuminance sensor present ({names}). Live lux "
                "is not read yet. The webcam is not used."
            ),
        )
    return LightCapability(
        supported=True,
        present=False,
        method="linux-iio",
        detail=(
            "No Linux IIO illuminance sensor found. The light signal is "
            "skipped. The webcam is not used."
        ),
    )


def _illuminance_devices(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    found: list[str] = []
    try:
        children = sorted(root.iterdir())
    except OSError:
        return []
    for device in children:
        for name in _IIO_FILES:
            candidate = device / name
            try:
                exists = candidate.is_file()
            except OSError:
                exists = False
            if exists:
                found.append(device.name)
                break
    return found
