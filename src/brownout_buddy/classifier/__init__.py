"""Outage classifier.

The core in v0.1 turns one sample into a label and a confidence score.
Internet coincidence and gateway ping are real signals. Ambient light,
the LAN sentinel, the tray question, and pattern memory are interfaces
with stub implementations: they can be injected by the simulator, and
live reads do not change the score.
"""

from brownout_buddy.classifier.engine import OutageClassifier, default_classifier
from brownout_buddy.classifier.light import LightCapability, detect_light
from brownout_buddy.classifier.ping import icmp_ping, ping_command
from brownout_buddy.classifier.prompt import StubConfirmationPrompt
from brownout_buddy.classifier.score import UPS_CAVEAT, score_readings
from brownout_buddy.classifier.signals import (
    GatewaySignal,
    InternetCoincidenceSignal,
    LightSensorSignal,
    PatternSignal,
    SentinelSignal,
)
from brownout_buddy.classifier.types import (
    Classification,
    ClassifyContext,
    Signal,
    SignalReading,
)

__all__ = [
    "Classification",
    "ClassifyContext",
    "GatewaySignal",
    "InternetCoincidenceSignal",
    "LightCapability",
    "LightSensorSignal",
    "OutageClassifier",
    "PatternSignal",
    "SentinelSignal",
    "Signal",
    "SignalReading",
    "StubConfirmationPrompt",
    "UPS_CAVEAT",
    "default_classifier",
    "detect_light",
    "icmp_ping",
    "ping_command",
    "score_readings",
]
