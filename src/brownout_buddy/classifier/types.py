"""Interfaces shared by classifier signals and the rule scorer.

A signal's ``read`` method returns a :class:`SignalReading`. The scorer
ignores a reading when ``stub`` is true or the state is ``unavailable``
or ``unknown``. That is how unfinished signals stay in the pipeline
without pretending to know something.

Simulator injections set ``stub`` false and a concrete state so the same
rules can be tested without hardware.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from brownout_buddy.models import NetworkStatus, OutageLabel, PowerSource


@dataclass(frozen=True)
class SignalReading:
    name: str
    state: str
    stub: bool
    detail: str
    source: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "state": self.state,
            "stub": self.stub,
            "detail": self.detail,
            "source": self.source,
        }


@dataclass
class ClassifyContext:
    """Facts available to every signal for one sample.

    ``gateway_reachable`` is an explicit override (the simulator, or a
    test). ``None`` means "not overridden": a live gateway signal may
    ping when ``probe_gateway`` is true, and otherwise reports unknown.

    ``light`` is ``"drop"`` or ``"steady"`` only when a caller injects it.
    ``sentinel`` is ``"silent"`` or ``"alive"`` only when injected.
    ``history`` is accepted for the pattern signal. v0.1 does not read it.
    """

    previous_power: PowerSource
    power: PowerSource
    previous_network: NetworkStatus
    network: NetworkStatus
    gateway_host: str | None = None
    gateway_reachable: bool | None = None
    probe_gateway: bool = False
    ping_timeout: float = 1.0
    light: str | None = None
    sentinel: str | None = None
    sentinel_configured: bool = False
    sentinel_host: str = ""
    light_enabled: bool = True
    history: tuple[object, ...] = field(default_factory=tuple)


class Signal(Protocol):
    """One input to the scorer. Implementations must not use the webcam."""

    name: str

    def read(self, ctx: ClassifyContext) -> SignalReading:
        """Observe this signal. Do not raise for a missing device."""


@dataclass(frozen=True)
class Classification:
    label: OutageLabel
    confidence: float
    leading: OutageLabel
    votes: dict[str, float]
    readings: tuple[SignalReading, ...]
    prompt: bool
    question: str | None
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label.value,
            "confidence": self.confidence,
            "leading": self.leading.value,
            "votes": dict(self.votes),
            "prompt": self.prompt,
            "question": self.question,
            "notes": list(self.notes),
            "readings": [reading.as_dict() for reading in self.readings],
        }
