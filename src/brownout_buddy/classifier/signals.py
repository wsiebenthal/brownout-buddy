"""Built-in signals.

Internet coincidence and gateway reachability are live. The other three
classes exist so the scorer, the simulator, and later milestones share one
``read(ctx)`` shape. Their live result is a stub and is not scored.
"""

from __future__ import annotations

from brownout_buddy.classifier.light import detect_light
from brownout_buddy.classifier.ping import icmp_ping
from brownout_buddy.classifier.types import ClassifyContext, SignalReading
from brownout_buddy.models import NetworkStatus, PowerSource

_LOST = frozenset({NetworkStatus.INTERNET_DOWN, NetworkStatus.LAN_DOWN})


class InternetCoincidenceSignal:
    """Whether connectivity dropped in the same sample as AC power."""

    name = "internet_coincidence"

    def read(self, ctx: ClassifyContext) -> SignalReading:
        ac_lost = (
            ctx.previous_power == PowerSource.AC and ctx.power == PowerSource.BATTERY
        )
        was_online = ctx.previous_network == NetworkStatus.ONLINE
        connectivity_lost = was_online and ctx.network in _LOST
        internet_up = ctx.network == NetworkStatus.ONLINE
        if ac_lost and connectivity_lost:
            state = "coinciding"
            detail = "Internet or LAN failed in the same sample as the switch to battery."
        elif ac_lost and internet_up:
            state = "still_up"
            detail = "The computer lost AC and connectivity was still up."
        elif ac_lost:
            state = "ac_only"
            detail = "The computer lost AC. Connectivity did not clearly drop or stay up."
        elif connectivity_lost:
            state = "internet_only"
            detail = "Connectivity failed without a switch from AC to battery."
        else:
            state = "not_applicable"
            detail = "This sample has no new power or connectivity loss to compare."
        return SignalReading(
            name=self.name,
            state=state,
            stub=False,
            detail=detail,
            source="sample",
        )


class GatewaySignal:
    """Ping the default gateway, or use an explicit simulator override.

    ``pinger`` returning None means the ping could not be run. That is
    reported as unknown, not as a dead router. Pass a callable for tests.
    When ``pinger`` is None, :func:`icmp_ping` is called at read time.
    """

    name = "gateway"

    def __init__(self, pinger=None):
        self._pinger = pinger

    def read(self, ctx: ClassifyContext) -> SignalReading:
        if ctx.gateway_reachable is not None:
            state = "up" if ctx.gateway_reachable else "down"
            detail = (
                "Gateway reachability was supplied by the simulator or a test."
            )
            if state == "up":
                detail += " " + (
                    "A router on a UPS can stay up through a brownout."
                )
            return SignalReading(
                name=self.name,
                state=state,
                stub=False,
                detail=detail,
                source="simulator",
            )
        if not ctx.probe_gateway:
            return SignalReading(
                name=self.name,
                state="unknown",
                stub=False,
                detail="No gateway reading was supplied, and this sample did not ping.",
                source="none",
            )
        host = ctx.gateway_host
        if not host or host == "0.0.0.0":
            return SignalReading(
                name=self.name,
                state="unknown",
                stub=False,
                detail="No default gateway address to ping.",
                source="none",
            )
        pinger = self._pinger or icmp_ping
        try:
            answered = pinger(host, ctx.ping_timeout)
        except Exception as exc:  # a signal must not take down the monitor
            return SignalReading(
                name=self.name,
                state="unknown",
                stub=False,
                detail=f"Gateway ping failed before it could run ({exc.__class__.__name__}).",
                source="ping-error",
            )
        if answered is None:
            return SignalReading(
                name=self.name,
                state="unknown",
                stub=False,
                detail=(
                    f"Could not ping {host}. The router is not marked down just "
                    "because ping could not be run."
                ),
                source="ping-unavailable",
            )
        if answered:
            return SignalReading(
                name=self.name,
                state="up",
                stub=False,
                detail=(
                    f"Gateway {host} answered a ping. A router on a UPS can stay "
                    "up through a brownout."
                ),
                source="icmp",
            )
        return SignalReading(
            name=self.name,
            state="down",
            stub=False,
            detail=f"Gateway {host} did not answer a ping.",
            source="icmp",
        )


class LightSensorSignal:
    """Ambient light. Live lux is not read. Injected drop/steady is scored."""

    name = "ambient_light"

    def __init__(self, enabled: bool = True, detect=detect_light):
        self._enabled = enabled
        self._detect = detect

    def read(self, ctx: ClassifyContext) -> SignalReading:
        if ctx.light == "drop":
            return SignalReading(
                name=self.name,
                state="dropped",
                stub=False,
                detail="Ambient light drop supplied by the simulator.",
                source="simulator",
            )
        if ctx.light == "steady":
            return SignalReading(
                name=self.name,
                state="steady",
                stub=False,
                detail="Steady ambient light supplied by the simulator.",
                source="simulator",
            )
        if not self._enabled or not ctx.light_enabled:
            return SignalReading(
                name=self.name,
                state="unavailable",
                stub=True,
                detail="Ambient light checks are disabled. The webcam is not used.",
                source="disabled",
            )
        capability = self._detect()
        return SignalReading(
            name=self.name,
            state="unavailable",
            stub=True,
            detail=capability.detail + " This reading is a stub and is not scored.",
            source=capability.method,
        )


class SentinelSignal:
    """LAN heartbeat companion. v0.1 does not contact the device."""

    name = "sentinel"

    def __init__(self, enabled: bool = False, host: str = ""):
        self._enabled = enabled
        self._host = host

    def read(self, ctx: ClassifyContext) -> SignalReading:
        if ctx.sentinel == "silent":
            return SignalReading(
                name=self.name,
                state="silent",
                stub=False,
                detail="Sentinel silence supplied by the simulator.",
                source="simulator",
            )
        if ctx.sentinel == "alive":
            return SignalReading(
                name=self.name,
                state="alive",
                stub=False,
                detail="Sentinel heartbeat supplied by the simulator.",
                source="simulator",
            )
        configured = ctx.sentinel_configured or self._enabled
        host = ctx.sentinel_host or self._host
        if configured and host:
            detail = (
                f"Sentinel {host} is configured, but the heartbeat watcher is "
                "not implemented yet. The host was not contacted."
            )
        else:
            detail = (
                "No sentinel is configured. The heartbeat watcher is not "
                "implemented yet."
            )
        return SignalReading(
            name=self.name,
            state="unavailable",
            stub=True,
            detail=detail,
            source="stub",
        )


class PatternSignal:
    """History habits. The ``history`` field is accepted and not read."""

    name = "pattern"

    def read(self, ctx: ClassifyContext) -> SignalReading:
        # History is part of the interface for a later milestone. Counting it
        # here would be an unimplemented heuristic, so the value is unused.
        _ = ctx.history
        return SignalReading(
            name=self.name,
            state="unavailable",
            stub=True,
            detail=(
                "Time-of-day unplug habits and outage clustering are not "
                "implemented yet."
            ),
            source="stub",
        )
