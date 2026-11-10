"""Outage state machine.

A power outage opens only on a seen transition from AC to battery. Losing
the battery sensor (``unknown``) does not open or close anything. Network
outages open when the debounced status becomes ``internet_down`` or
``lan_down``. Switching between those two closes one row and opens the other
so the log keeps a single type per row.

The first sample after startup is a baseline: it sets the current state and
does not invent an outage for time the app did not observe. The simulator
seeds an explicit "on AC and online" baseline so a demo can open an outage
immediately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from brownout_buddy.models import (
    NetworkStatus,
    OpenOutage,
    OutageEnded,
    OutageStarted,
    OutageType,
    PowerSource,
)

Event = OutageStarted | OutageEnded

_CONNECTIVITY = {
    NetworkStatus.INTERNET_DOWN: OutageType.INTERNET,
    NetworkStatus.LAN_DOWN: OutageType.LAN,
}


@dataclass
class Debouncer:
    """Hold a network status until it repeats for the configured polls.

    ``unknown`` polls are ignored so a probe error does not look like an
    outage or a recovery. The first :meth:`push` seeds the stable status
    immediately; thresholds apply to later changes. Call :meth:`seed` after
    the simulator forces a state.
    """

    failure_threshold: int
    recovery_threshold: int
    stable: NetworkStatus = NetworkStatus.UNKNOWN
    pending: NetworkStatus | None = None
    count: int = 0
    seeded: bool = False

    def seed(self, status: NetworkStatus) -> None:
        self.stable = status
        self.pending = None
        self.count = 0
        self.seeded = True

    def push(self, status: NetworkStatus) -> NetworkStatus:
        if not self.seeded:
            self.seed(status)
            return self.stable
        if status == NetworkStatus.UNKNOWN or status == self.stable:
            self.pending = None
            self.count = 0
            return self.stable
        if self.pending != status:
            self.pending = status
            self.count = 1
        else:
            self.count += 1
        needed = (
            self.recovery_threshold
            if status == NetworkStatus.ONLINE
            else self.failure_threshold
        )
        if self.count >= needed:
            self.stable = status
            self.pending = None
            self.count = 0
        return self.stable


@dataclass
class Tracker:
    """In-memory outage intervals. Persistence is the store's job."""

    power: PowerSource = PowerSource.AC
    network: NetworkStatus = NetworkStatus.ONLINE
    seeded: bool = False
    open_outages: dict[OutageType, OpenOutage] = field(default_factory=dict)

    def seed(self, power: PowerSource, network: NetworkStatus) -> None:
        self.power = power
        self.network = network
        self.seeded = True

    def apply(
        self, power: PowerSource, network: NetworkStatus, at: datetime
    ) -> list[Event]:
        if at.tzinfo is None:
            raise ValueError("outage timestamps must be timezone-aware")
        if not self.seeded:
            self.seed(power, network)
            return []
        events: list[Event] = []
        events.extend(self._apply_power(power, at))
        events.extend(self._apply_network(network, at))
        return events

    def set_open_id(self, outage_type: OutageType, outage_id: int) -> None:
        self.open_outages[outage_type].id = outage_id

    def _apply_power(self, power: PowerSource, at: datetime) -> list[Event]:
        if power == PowerSource.UNKNOWN or power == self.power:
            return []
        events: list[Event] = []
        if self.power == PowerSource.AC and power == PowerSource.BATTERY:
            events.append(self._open(OutageType.POWER, at))
        elif self.power == PowerSource.BATTERY and power == PowerSource.AC:
            ended = self._close(OutageType.POWER, at)
            if ended is not None:
                events.append(ended)
        self.power = power
        return events

    def _apply_network(self, network: NetworkStatus, at: datetime) -> list[Event]:
        if network == NetworkStatus.UNKNOWN or network == self.network:
            return []
        events: list[Event] = []
        current = self._open_connectivity()
        desired = _CONNECTIVITY.get(network)
        if current is not None and (desired is None or current != desired):
            ended = self._close(current, at)
            if ended is not None:
                events.append(ended)
        if desired is not None and desired not in self.open_outages:
            events.append(self._open(desired, at))
        self.network = network
        return events

    def _open_connectivity(self) -> OutageType | None:
        for outage_type in (OutageType.INTERNET, OutageType.LAN):
            if outage_type in self.open_outages:
                return outage_type
        return None

    def _open(self, outage_type: OutageType, at: datetime) -> OutageStarted:
        outage = OpenOutage(type=outage_type, started_at=at)
        self.open_outages[outage_type] = outage
        return OutageStarted(type=outage_type, started_at=at, outage=outage)

    def _close(self, outage_type: OutageType, at: datetime) -> OutageEnded | None:
        outage = self.open_outages.pop(outage_type, None)
        if outage is None:
            return None
        return OutageEnded(
            id=outage.id,
            type=outage_type,
            started_at=outage.started_at,
            ended_at=at,
        )
