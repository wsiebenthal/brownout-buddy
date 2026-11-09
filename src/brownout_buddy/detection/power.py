"""Power-source detection.

Version 0.1 asks psutil for ``sensors_battery()`` on every OS. That is
enough to notice an AC-to-battery transition on a laptop that exposes one
battery. It does not subscribe to native power events, so a machine can
change state between polls, and a desktop with no battery reports
``unknown`` rather than a fake "on AC" reading.

Native hooks (IOKit, WM_POWERBROADCAST, UPower) are tracked in the roadmap.
"""

from __future__ import annotations

from brownout_buddy.models import PowerReading, PowerSource

# psutil uses these sentinels for secsleft. Duplicated here so the pure
# interpreter does not import psutil.
POWER_TIME_UNKNOWN = -1
POWER_TIME_UNLIMITED = -2


def interpret_battery(
    plugged: bool | None,
    percent: float | None = None,
    secsleft: int | None = None,
    *,
    method: str = "psutil",
    note: str = "",
) -> PowerReading:
    """Map a battery sample onto a :class:`PowerReading`.

    ``plugged is None`` means the OS did not report a battery. Negative
    ``secsleft`` values match psutil's unknown and unlimited sentinels and
    become ``None`` so callers never display a negative time.
    """

    if plugged is None:
        source = PowerSource.UNKNOWN
    elif plugged:
        source = PowerSource.AC
    else:
        source = PowerSource.BATTERY

    seconds: int | None
    if secsleft is None or secsleft < 0 or secsleft in (
        POWER_TIME_UNKNOWN,
        POWER_TIME_UNLIMITED,
    ):
        seconds = None
    else:
        seconds = int(secsleft)

    pct = None if percent is None else float(percent)
    return PowerReading(
        source=source,
        percent=pct,
        seconds_left=seconds,
        method=method,
        note=note,
    )


def read_power() -> PowerReading:
    """Read the current power source. Never raises for a missing battery."""

    try:
        import psutil
    except ImportError:
        return interpret_battery(
            None,
            method="unavailable",
            note="psutil is not installed; power source is unknown.",
        )

    try:
        battery = psutil.sensors_battery()
    except Exception as exc:  # pragma: no cover - OS-specific failure
        return interpret_battery(
            None,
            method="psutil-error",
            note=f"psutil could not read the battery ({exc.__class__.__name__}).",
        )

    if battery is None:
        return interpret_battery(
            None,
            method="psutil",
            note="No battery reported. Desktops and some VMs look like this; it is not an outage.",
        )

    return interpret_battery(
        bool(battery.power_plugged),
        percent=battery.percent,
        secsleft=battery.secsleft,
        method="psutil",
    )
