"""Power-source detection.

Version 0.1 asks psutil for ``sensors_battery()`` on every OS. That is
enough to notice an AC-to-battery transition on a laptop that exposes one
battery. It does not subscribe to native power events, so a machine can
change state between polls, and a desktop with no battery reports
``unknown`` rather than a fake "on AC" reading.

On Windows it first takes a ``GetSystemPowerStatus`` snapshot through
ctypes and only falls back to psutil if that call fails. Native event
hooks (IOKit, WM_POWERBROADCAST, UPower) are tracked in the roadmap.
"""

from __future__ import annotations

import sys

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


# SYSTEM_POWER_STATUS values from GetSystemPowerStatus.
_WIN_AC_OFFLINE = 0
_WIN_AC_ONLINE = 1
_WIN_FLAG_NO_BATTERY = 128
_WIN_UNKNOWN_BYTE = 255
_WIN_UNKNOWN_DWORD = 0xFFFFFFFF


def interpret_windows_power_status(
    ac_line_status: int,
    battery_flag: int,
    life_percent: int,
    life_time: int,
) -> PowerReading:
    """Map Windows ``SYSTEM_POWER_STATUS`` fields onto a reading.

    A machine with no system battery stays ``unknown`` even when
    ``ACLineStatus`` says online. That matches the psutil path: a desktop
    has nothing to fall back to, so it never logs an unplug.
    """

    method = "win32"
    if battery_flag == _WIN_FLAG_NO_BATTERY:
        return interpret_battery(
            None,
            method=method,
            note="No system battery reported. Desktops and some VMs look like this; it is not an outage.",
        )

    plugged: bool | None
    if ac_line_status == _WIN_AC_ONLINE:
        plugged = True
    elif ac_line_status == _WIN_AC_OFFLINE:
        plugged = False
    else:
        plugged = None

    percent = None if life_percent == _WIN_UNKNOWN_BYTE else life_percent
    secsleft = None if life_time == _WIN_UNKNOWN_DWORD else life_time
    note = "" if plugged is not None else "Windows reported an unknown AC line status."
    return interpret_battery(
        plugged,
        percent=percent,
        secsleft=secsleft,
        method=method,
        note=note,
    )


def _read_power_windows() -> PowerReading | None:  # pragma: no cover - Windows only
    """Snapshot ``GetSystemPowerStatus``. Returns ``None`` if the call fails."""

    import ctypes
    from ctypes import wintypes

    class SystemPowerStatus(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_ubyte),
            ("BatteryFlag", ctypes.c_ubyte),
            ("BatteryLifePercent", ctypes.c_ubyte),
            ("SystemStatusFlag", ctypes.c_ubyte),
            ("BatteryLifeTime", wintypes.DWORD),
            ("BatteryFullLifeTime", wintypes.DWORD),
        ]

    status = SystemPowerStatus()
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ok = kernel32.GetSystemPowerStatus(ctypes.byref(status))
    except (OSError, AttributeError):
        return None
    if not ok:
        return None
    return interpret_windows_power_status(
        status.ACLineStatus,
        status.BatteryFlag,
        status.BatteryLifePercent,
        status.BatteryLifeTime,
    )


def read_power() -> PowerReading:
    """Read the current power source. Never raises for a missing battery."""

    if sys.platform == "win32":
        reading = _read_power_windows()
        if reading is not None:
            return reading

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
