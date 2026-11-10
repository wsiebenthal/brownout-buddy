"""Run a list of signals and score whatever they return."""

from __future__ import annotations

from brownout_buddy.classifier.score import score_readings
from brownout_buddy.classifier.signals import (
    GatewaySignal,
    InternetCoincidenceSignal,
    LightSensorSignal,
    PatternSignal,
    SentinelSignal,
)
from brownout_buddy.classifier.types import Classification, ClassifyContext, Signal
from brownout_buddy.config import Config


class OutageClassifier:
    """Pluggable classifier. Replace ``signals`` to add or remove inputs."""

    def __init__(
        self,
        signals: list[Signal],
        *,
        min_score: float = 0.55,
        min_margin: float = 0.15,
        prompt_below: float = 0.6,
        enabled: bool = True,
    ):
        self.signals = list(signals)
        self.min_score = min_score
        self.min_margin = min_margin
        self.prompt_below = prompt_below
        self.enabled = enabled

    def classify(self, ctx: ClassifyContext) -> Classification | None:
        if not self.enabled:
            return None
        readings = tuple(signal.read(ctx) for signal in self.signals)
        return score_readings(
            readings,
            min_score=self.min_score,
            min_margin=self.min_margin,
            prompt_below=self.prompt_below,
        )


def default_classifier(config: Config, pinger=None) -> OutageClassifier:
    """The v0.1 signal list: two live signals and three stubs."""

    return OutageClassifier(
        signals=[
            InternetCoincidenceSignal(),
            GatewaySignal(pinger=pinger),
            LightSensorSignal(enabled=config.light_enabled),
            SentinelSignal(enabled=config.sentinel_enabled, host=config.sentinel_host),
            PatternSignal(),
        ],
        min_score=config.classifier_min_score,
        min_margin=config.classifier_min_margin,
        prompt_below=config.classifier_prompt_below,
        enabled=config.classifier_enabled,
    )
