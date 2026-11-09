"""Rule-based scoring.

Weights are basis points (100 = a full point of confidence) so the totals
do not drift through binary fractions. A published label other than
``unknown`` needs ``min_score`` and a lead of ``min_margin`` over the next
label. Confidence is capped at 0.95: these rules are not certain.

Votes, in points:

* AC lost and connectivity lost on the same sample: brownout +35.
* AC lost and gateway down: brownout +40.
* AC lost and an injected light drop: brownout +25.
* AC lost and an injected silent sentinel: brownout +30.
* AC lost and gateway up: unplugged +45.
* AC lost and internet still up: unplugged +35.
* AC lost and an injected steady light: unplugged +15.
* AC lost and an injected live sentinel: unplugged +25.
* Connectivity lost, AC still present, gateway up: isp-outage +70.
* Connectivity lost, AC still present, gateway unknown: isp-outage +30.

Stub readings never add points. A router on a UPS stays up during a real
brownout, which removes the gateway vote; that caveat is attached whenever
AC was lost and the gateway answered.
"""

from __future__ import annotations

from brownout_buddy.classifier.types import Classification, SignalReading
from brownout_buddy.models import OutageLabel

UPS_CAVEAT = (
    "A router on a UPS stays reachable during a real brownout, so a live "
    "gateway cannot by itself prove the laptop was only unplugged."
)

_PROMPT = "Brownout or unplugged?"
_CONFIDENCE_CAP_POINTS = 95

# Usable states. Anything else, including "unavailable" and "unknown", is ignored.
_INTERNET_AC_LOST = frozenset({"coinciding", "still_up", "ac_only"})
_INTERNET_LOST = frozenset({"coinciding", "internet_only"})


def score_readings(
    readings: tuple[SignalReading, ...] | list[SignalReading],
    *,
    min_score: float = 0.55,
    min_margin: float = 0.15,
    prompt_below: float = 0.6,
) -> Classification:
    """Score a sample. Unknown signal names are ignored."""

    by_name = {reading.name: reading for reading in readings}
    internet = _usable_state(by_name.get("internet_coincidence"))
    gateway = _usable_state(by_name.get("gateway"))
    light = _usable_state(by_name.get("ambient_light"))
    sentinel = _usable_state(by_name.get("sentinel"))

    ac_lost = internet in _INTERNET_AC_LOST
    connectivity_lost = internet in _INTERNET_LOST
    votes = {
        OutageLabel.BROWNOUT.value: 0,
        OutageLabel.UNPLUGGED.value: 0,
        OutageLabel.ISP_OUTAGE.value: 0,
    }

    if ac_lost and internet == "coinciding":
        votes[OutageLabel.BROWNOUT.value] += 35
    if ac_lost and gateway == "down":
        votes[OutageLabel.BROWNOUT.value] += 40
    if ac_lost and light == "dropped":
        votes[OutageLabel.BROWNOUT.value] += 25
    if ac_lost and sentinel == "silent":
        votes[OutageLabel.BROWNOUT.value] += 30

    if ac_lost and gateway == "up":
        votes[OutageLabel.UNPLUGGED.value] += 45
    if ac_lost and internet == "still_up":
        votes[OutageLabel.UNPLUGGED.value] += 35
    if ac_lost and light == "steady":
        votes[OutageLabel.UNPLUGGED.value] += 15
    if ac_lost and sentinel == "alive":
        votes[OutageLabel.UNPLUGGED.value] += 25

    if not ac_lost and connectivity_lost and gateway == "up":
        votes[OutageLabel.ISP_OUTAGE.value] += 70
    elif not ac_lost and connectivity_lost and gateway not in {"up", "down"}:
        votes[OutageLabel.ISP_OUTAGE.value] += 30

    ranking = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
    top_name, top_points = ranking[0]
    second_points = ranking[1][1]
    min_points = _points(min_score)
    margin_points = _points(min_margin)
    if top_points == 0:
        label = OutageLabel.UNKNOWN
        leading = OutageLabel.UNKNOWN
        confidence_points = 0
    elif top_points < min_points or (top_points - second_points) < margin_points:
        label = OutageLabel.UNKNOWN
        leading = OutageLabel(top_name)
        confidence_points = top_points
    else:
        label = OutageLabel(top_name)
        leading = label
        confidence_points = min(top_points, _CONFIDENCE_CAP_POINTS)
    confidence = _score(confidence_points)

    prompt = ac_lost and (
        label is OutageLabel.UNKNOWN or confidence_points <= _points(prompt_below)
    )
    notes: list[str] = []
    if ac_lost and gateway == "up":
        notes.append(UPS_CAVEAT)
    if ac_lost and internet == "still_up" and gateway == "down":
        notes.append(
            "Internet is up but the gateway did not answer. Those signals "
            "disagree, so this sample is not treated as a clear unplug or brownout."
        )
    if not ac_lost and connectivity_lost and gateway == "down":
        notes.append(
            "The gateway is down while mains power is still present. That looks "
            "like a local network problem, not an ISP outage or a brownout."
        )
    return Classification(
        label=label,
        confidence=confidence,
        leading=leading,
        votes={name: _score(points) for name, points in votes.items()},
        readings=tuple(readings),
        prompt=prompt,
        question=_PROMPT if prompt else None,
        notes=tuple(notes),
    )


def _usable_state(reading: SignalReading | None) -> str | None:
    if reading is None or reading.stub:
        return None
    if reading.state in {"unavailable", "unknown", "not_applicable"}:
        return None
    return reading.state


def _points(score: float) -> int:
    return int(round(score * 100))


def _score(points: int) -> float:
    return points / 100
