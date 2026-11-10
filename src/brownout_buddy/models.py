"""Shared enums and records.

These types are the contract between detection, the outage tracker, the
log, and the tray. They contain no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PowerSource(str, Enum):
    """Where the computer is drawing power from."""

    AC = "ac"
    BATTERY = "battery"
    UNKNOWN = "unknown"


class NetworkStatus(str, Enum):
    """Result of the connectivity heuristic.

    ``internet_down`` means a configured LAN check (or the default route,
    where that can be read) still looks up, but every internet probe failed.
    ``lan_down`` means the local network itself looks down.
    """

    ONLINE = "online"
    INTERNET_DOWN = "internet_down"
    LAN_DOWN = "lan_down"
    UNKNOWN = "unknown"


class OutageType(str, Enum):
    """One row in the outage log."""

    POWER = "power"
    INTERNET = "internet"
    LAN = "lan"


class OutageLabel(str, Enum):
    """What the classifier thinks an outage was.

    ``unknown`` means the rule score was too weak or the signals disagreed.
    It is not a failure to store the row. The model label stays even after
    the user sets a ground-truth answer.
    """

    BROWNOUT = "brownout"
    UNPLUGGED = "unplugged"
    ISP_OUTAGE = "isp-outage"
    UNKNOWN = "unknown"


class TrayState(str, Enum):
    """Icon shown in the menu bar / system tray.

    Precedence is paused, then offline (LAN or upstream), then on battery,
    then normal. A machine that is both on battery and offline shows offline;
    the menu text still lists both facts.
    """

    NORMAL = "normal"
    ON_BATTERY = "on_battery"
    OFFLINE = "offline"
    PAUSED = "paused"


def tray_state(
    power: PowerSource, network: NetworkStatus, paused: bool
) -> TrayState:
    if paused:
        return TrayState.PAUSED
    if network in (NetworkStatus.INTERNET_DOWN, NetworkStatus.LAN_DOWN):
        return TrayState.OFFLINE
    if power == PowerSource.BATTERY:
        return TrayState.ON_BATTERY
    return TrayState.NORMAL


@dataclass
class PowerReading:
    source: PowerSource
    percent: float | None = None
    seconds_left: int | None = None
    method: str = "none"
    note: str = ""


@dataclass(frozen=True)
class RouteInfo:
    """What the process could learn about a default route.

    ``checked`` is False on platforms where v0.1 does not read the routing
    table. ``has_default_route`` is then None and must not be treated as
    proof that the LAN is down.
    """

    checked: bool
    has_default_route: bool | None
    gateway: str | None
    method: str


@dataclass
class NetworkReading:
    status: NetworkStatus
    internet_results: list[bool] = field(default_factory=list)
    lan_results: list[bool] | None = None
    route: RouteInfo | None = None
    note: str = ""


@dataclass
class OpenOutage:
    type: OutageType
    started_at: datetime
    id: int | None = None


@dataclass
class OutageStarted:
    type: OutageType
    started_at: datetime
    outage: OpenOutage


@dataclass
class OutageEnded:
    id: int | None
    type: OutageType
    started_at: datetime
    ended_at: datetime

    @property
    def duration_seconds(self) -> int:
        return max(0, int((self.ended_at - self.started_at).total_seconds()))


@dataclass(frozen=True)
class OutageRecord:
    id: int
    type: OutageType
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    source: str
    detail: dict[str, object]
    label: str | None = None
    confidence: float | None = None
    ground_truth: str | None = None
    signals: dict[str, object] = field(default_factory=dict)

    def elapsed_seconds(self, now: datetime) -> int:
        end = self.ended_at if self.ended_at is not None else now
        return max(0, int((end - self.started_at).total_seconds()))

    @property
    def open(self) -> bool:
        return self.ended_at is None
