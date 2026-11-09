"""Monitor loop: read sensors, track intervals, classify, store.

The simulator calls :meth:`Monitor.simulate` and never pings the network
or runs protect-work commands. Live polls do both.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from brownout_buddy.actions import ActionExecutor, ActionResult, plan_actions
from brownout_buddy.classifier.engine import OutageClassifier, default_classifier
from brownout_buddy.classifier.types import Classification, ClassifyContext
from brownout_buddy.config import Config
from brownout_buddy.detection.network import read_network
from brownout_buddy.detection.power import read_power
from brownout_buddy.models import (
    NetworkReading,
    NetworkStatus,
    OutageStarted,
    PowerReading,
    PowerSource,
    TrayState,
    tray_state,
)
from brownout_buddy.store import OutageStore
from brownout_buddy.tracking import Debouncer, Event, Tracker

SCENARIOS = (
    "power-loss",
    "unplug",
    "offline",
    "internet-down",
    "lan-down",
    "restore",
)


def current_time() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PollResult:
    baseline: bool
    paused: bool
    seeded: bool
    at: datetime
    power: PowerReading
    network: NetworkReading
    events: list[Event]
    actions: list[ActionResult]
    classification: Classification | None
    tray: TrayState

    @property
    def changed(self) -> bool:
        return self.baseline or bool(self.events)


class Monitor:
    def __init__(
        self,
        config: Config,
        store: OutageStore,
        *,
        power_reader=None,
        network_reader=None,
        classifier: OutageClassifier | None = None,
        executor: ActionExecutor | None = None,
        clock=current_time,
    ):
        self.config = config
        self.store = store
        self.power_reader = power_reader or read_power
        self.network_reader = network_reader or (lambda: read_network(config))
        self.classifier = classifier or default_classifier(config)
        self.executor = executor or ActionExecutor(
            timeout=config.command_timeout_seconds
        )
        self.clock = clock
        self._lock = threading.RLock()
        self.debouncer = Debouncer(
            config.failure_threshold, config.recovery_threshold
        )
        loaded = store.load(self.debouncer)
        if loaded is None:
            self.tracker = Tracker()
            self.paused = store.is_paused()
            self.last_power = PowerReading(PowerSource.UNKNOWN, method="none")
            self.last_network = NetworkReading(NetworkStatus.UNKNOWN)
        else:
            self.tracker = loaded.tracker
            self.paused = loaded.paused
            self.last_power = PowerReading(
                loaded.tracker.power,
                percent=loaded.battery_percent,
                seconds_left=loaded.battery_seconds_left,
                method="stored",
                note=loaded.power_note,
            )
            self.last_network = NetworkReading(
                status=loaded.tracker.network,
                note=loaded.network_note,
            )
        self.last_classification: Classification | None = None

    def recent(self, limit: int = 5):
        with self._lock:
            return self.store.recent(limit=limit)

    def pending_question(self):
        """Latest low-confidence classification and the open outage ids, if any."""

        with self._lock:
            classification = self.last_classification
            if classification is None or not classification.prompt:
                return None
            ids = [record.id for record in self.store.open_records()]
            return classification, ids

    def set_paused(self, paused: bool, at: datetime | None = None) -> None:
        with self._lock:
            moment = at or self.clock()
            self.paused = paused
            self.store.set_paused(paused, moment)

    def poll(self) -> PollResult:
        """One live sample. Honors pause and does not invent a past outage."""

        with self._lock:
            self.paused = self.store.is_paused()
            now = self.clock()
            if self.paused:
                return self._result(
                    now=now,
                    power=self.last_power,
                    network=self.last_network,
                    events=[],
                    actions=[],
                    classification=None,
                    baseline=False,
                )
            power = self._read_power()
            network = self._read_network()
            if not self.tracker.seeded:
                self._seed_live(power, network)
                self._remember(power, network)
                self.store.persist(
                    self.tracker,
                    self.debouncer,
                    [],
                    paused=self.paused,
                    updated_at=now,
                    power=self.last_power,
                    network_note=self.last_network.note,
                    source="live",
                    detail={},
                )
                return self._result(
                    now=now,
                    power=self.last_power,
                    network=self.last_network,
                    events=[],
                    actions=[],
                    classification=None,
                    baseline=True,
                )
            previous_power = self.tracker.power
            previous_network = self.tracker.network
            stable = (
                self.debouncer.push(network.status)
                if self.config.network_enabled
                else self.tracker.network
            )
            power_source = (
                power.source if self.config.power_enabled else self.tracker.power
            )
            events = self.tracker.apply(power_source, stable, now)
            observed = NetworkReading(
                status=stable,
                internet_results=network.internet_results,
                lan_results=network.lan_results,
                route=network.route,
                note=network.note,
            )
            classification = self._classify(
                previous_power=previous_power,
                power=power_source,
                previous_network=previous_network,
                network=stable,
                network_reading=network,
                events=events,
                probe_gateway=True,
            )
            self._remember(power, observed)
            if classification is not None:
                self.last_classification = classification
            self.store.persist(
                self.tracker,
                self.debouncer,
                events,
                paused=self.paused,
                updated_at=now,
                power=self.last_power,
                network_note=self.last_network.note,
                source="live",
                detail=_detail(power, observed, "live", scenario=None),
                classification=None
                if classification is None
                else classification.as_dict(),
            )
            actions: list[ActionResult] = []
            if events:
                actions = self.executor.execute(
                    plan_actions(
                        events,
                        self.config,
                        self.last_power,
                        self.tracker.network,
                        classification,
                    )
                )
            return self._result(
                now=now,
                power=self.last_power,
                network=self.last_network,
                events=events,
                actions=actions,
                classification=classification if events else None,
                baseline=False,
            )

    def simulate(
        self,
        scenario: str,
        at: datetime | None = None,
        *,
        router_down: bool = False,
        router_up: bool = False,
        light_drop: bool = False,
        light_steady: bool = False,
        sentinel_silent: bool = False,
        sentinel_alive: bool = False,
        battery_percent: float | None = None,
        battery_minutes: float | None = None,
    ) -> PollResult:
        """Apply a scripted sample through the same tracker, scorer, and log.

        The simulator does not ping, does not read a light sensor, and does
        not run configured commands.
        """

        if scenario not in SCENARIOS:
            allowed = ", ".join(SCENARIOS)
            raise ValueError(f"unknown scenario {scenario!r}; expected one of: {allowed}")
        if router_down and router_up:
            raise ValueError("pass only one of router_down and router_up")
        if light_drop and light_steady:
            raise ValueError("pass only one of light_drop and light_steady")
        if sentinel_silent and sentinel_alive:
            raise ValueError("pass only one of sentinel_silent and sentinel_alive")
        if battery_percent is not None and not 0 <= battery_percent <= 100:
            raise ValueError("battery_percent must be from 0 to 100")
        with self._lock:
            now = at or self.clock()
            if not self.tracker.seeded:
                self.tracker.seed(PowerSource.AC, NetworkStatus.ONLINE)
                self.debouncer.seed(NetworkStatus.ONLINE)
            previous_power = self.tracker.power
            previous_network = self.tracker.network
            power_source, network_status, gateway = _scenario_targets(
                scenario,
                previous_power,
                previous_network,
                router_down=router_down,
                router_up=router_up,
            )
            seconds: int | None
            if battery_minutes is not None:
                seconds = int(battery_minutes * 60)
            elif scenario == "restore":
                seconds = None
            else:
                seconds = self.last_power.seconds_left
            percent = (
                battery_percent
                if battery_percent is not None
                else self.last_power.percent
            )
            power = PowerReading(
                source=power_source,
                percent=percent,
                seconds_left=seconds,
                method="simulator",
                note="Simulated power reading.",
            )
            network = NetworkReading(
                status=network_status,
                note="Simulated network state.",
            )
            events = self.tracker.apply(power_source, network_status, now)
            self.debouncer.seed(network_status)
            classification = self._classify(
                previous_power=previous_power,
                power=power_source,
                previous_network=previous_network,
                network=network_status,
                network_reading=network,
                events=events,
                probe_gateway=False,
                gateway_reachable=gateway,
                light="drop" if light_drop else "steady" if light_steady else None,
                sentinel=(
                    "silent" if sentinel_silent else "alive" if sentinel_alive else None
                ),
            )
            self._remember(power, network)
            if classification is not None:
                self.last_classification = classification
            self.store.persist(
                self.tracker,
                self.debouncer,
                events,
                paused=self.paused,
                updated_at=now,
                power=power,
                network_note=network.note,
                source="simulated",
                detail=_detail(power, network, "simulated", scenario=scenario),
                classification=None
                if classification is None
                else classification.as_dict(),
            )
            return self._result(
                now=now,
                power=power,
                network=network,
                events=events,
                actions=[],
                classification=classification if events else None,
                baseline=False,
            )

    def _classify(
        self,
        *,
        previous_power: PowerSource,
        power: PowerSource,
        previous_network: NetworkStatus,
        network: NetworkStatus,
        network_reading: NetworkReading,
        events: list[Event],
        probe_gateway: bool,
        gateway_reachable: bool | None = None,
        light: str | None = None,
        sentinel: str | None = None,
    ) -> Classification | None:
        if not any(isinstance(event, OutageStarted) for event in events):
            return None
        host = _gateway_host(network_reading, self.config)
        ctx = ClassifyContext(
            previous_power=previous_power,
            power=power,
            previous_network=previous_network,
            network=network,
            gateway_host=host,
            gateway_reachable=gateway_reachable,
            probe_gateway=probe_gateway,
            ping_timeout=self.config.network_timeout_seconds,
            light=light,
            sentinel=sentinel,
            sentinel_configured=self.config.sentinel_enabled,
            sentinel_host=self.config.sentinel_host,
            light_enabled=self.config.light_enabled,
            history=tuple(self.store.recent(limit=50)),
        )
        return self.classifier.classify(ctx)

    def _seed_live(self, power: PowerReading, network: NetworkReading) -> None:
        if self.config.network_enabled:
            stable = self.debouncer.push(network.status)
        else:
            stable = NetworkStatus.ONLINE
            self.debouncer.seed(stable)
        power_source = power.source if self.config.power_enabled else PowerSource.AC
        self.tracker.seed(power_source, stable)

    def _read_power(self) -> PowerReading:
        if not self.config.power_enabled:
            return PowerReading(
                source=PowerSource.UNKNOWN,
                method="disabled",
                note="Power monitoring is disabled in config.",
            )
        return self.power_reader()

    def _read_network(self) -> NetworkReading:
        if not self.config.network_enabled:
            return NetworkReading(
                status=NetworkStatus.UNKNOWN,
                note="Network monitoring is disabled in config.",
            )
        return self.network_reader()

    def _remember(self, power: PowerReading, network: NetworkReading) -> None:
        self.last_power = power
        self.last_network = network

    def _result(
        self,
        *,
        now: datetime,
        power: PowerReading,
        network: NetworkReading,
        events: list[Event],
        actions: list[ActionResult],
        classification: Classification | None,
        baseline: bool,
    ) -> PollResult:
        return PollResult(
            baseline=baseline,
            paused=self.paused,
            seeded=self.tracker.seeded,
            at=now,
            power=power,
            network=network,
            events=events,
            actions=actions,
            classification=classification,
            tray=self.tray,
        )

    @property
    def tray(self) -> TrayState:
        if not self.tracker.seeded and not self.paused:
            return TrayState.NORMAL
        return tray_state(self.tracker.power, self.tracker.network, self.paused)


def _scenario_targets(
    scenario: str,
    power: PowerSource,
    network: NetworkStatus,
    *,
    router_down: bool,
    router_up: bool,
) -> tuple[PowerSource, NetworkStatus, bool | None]:
    gateway: bool | None = None
    if scenario == "power-loss":
        power = PowerSource.BATTERY
    elif scenario == "unplug":
        power = PowerSource.BATTERY
        network = NetworkStatus.ONLINE
        gateway = True
    elif scenario in {"offline", "internet-down"}:
        network = NetworkStatus.INTERNET_DOWN
        gateway = True
    elif scenario == "lan-down":
        network = NetworkStatus.LAN_DOWN
        gateway = False
    elif scenario == "restore":
        power = PowerSource.AC
        network = NetworkStatus.ONLINE
        gateway = True
    if router_down:
        gateway = False
        if scenario != "restore":
            network = NetworkStatus.LAN_DOWN
    elif router_up:
        gateway = True
    return power, network, gateway


def _gateway_host(network: NetworkReading, config: Config) -> str | None:
    if network.route is not None and network.route.gateway:
        return network.route.gateway
    if config.lan_probes:
        return config.lan_probes[0].host
    return None


def _detail(
    power: PowerReading,
    network: NetworkReading,
    source: str,
    scenario: str | None,
) -> dict[str, object]:
    detail: dict[str, object] = {
        "source": source,
        "power": power.source.value,
        "power_method": power.method,
        "network": network.status.value,
    }
    if scenario:
        detail["scenario"] = scenario
    if power.percent is not None:
        detail["battery_percent"] = power.percent
    if power.seconds_left is not None:
        detail["battery_seconds_left"] = power.seconds_left
    if power.note:
        detail["power_note"] = power.note
    if network.note:
        detail["network_note"] = network.note
    if network.route is not None and network.route.gateway:
        detail["gateway"] = network.route.gateway
    return detail
