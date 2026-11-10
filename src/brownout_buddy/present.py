"""Text and JSON views of the log. No charts in v0.1."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from brownout_buddy import __version__
from brownout_buddy.actions import ActionResult, format_duration
from brownout_buddy.classifier.prompt import StubConfirmationPrompt
from brownout_buddy.models import OutageEnded, OutageRecord, OutageStarted, PowerReading
from brownout_buddy.monitor import Monitor, PollResult
from brownout_buddy.store import StatBucket
from brownout_buddy.tracking import Event


def zone_for(name: str):
    if name:
        return ZoneInfo(name)
    current = datetime.now().astimezone().tzinfo
    return current if current is not None else timezone.utc


def format_poll(monitor: Monitor, result: PollResult) -> str:
    lines: list[str] = []
    if result.baseline:
        lines.append(
            "Recorded a baseline. Outages already underway are not backfilled."
        )
    if result.paused and not result.events:
        lines.append("Monitoring is paused. No sample was taken.")
    for event in result.events:
        lines.append(_format_event(event))
    if result.classification is not None:
        lines.extend(_format_classification(result))
    for action in result.actions:
        lines.append(f"action {action.name}: {action.status}: {action.message}")
    if result.changed or result.classification is not None:
        lines.append("")
    lines.append(format_status(monitor, result.at))
    return "\n".join(lines)


def format_status(monitor: Monitor, now: datetime | None = None) -> str:
    moment = now or monitor.clock()
    zone = zone_for(monitor.config.timezone)
    power = monitor.last_power
    lines = [
        f"Brownout Buddy {__version__}",
        f"database: {monitor.store.path}",
        "config: "
        + (
            str(monitor.config.config_path)
            if monitor.config.config_path
            else "built-in defaults"
        ),
        f"tray: {monitor.tray.value}",
        f"power: {monitor.tracker.power.value if monitor.tracker.seeded else 'unknown'}",
        _battery_line(power),
        f"network: {monitor.tracker.network.value if monitor.tracker.seeded else 'unknown'}",
        f"paused: {'yes' if monitor.paused else 'no'}",
        f"seeded: {'yes' if monitor.tracker.seeded else 'no'}",
    ]
    if power.note:
        lines.append(f"power note: {power.note}")
    if monitor.last_network.note:
        lines.append(f"network note: {monitor.last_network.note}")
    open_rows = monitor.store.open_records()
    if not open_rows:
        lines.append("open outages: none")
    else:
        lines.append("open outages:")
        for record in open_rows:
            lines.append("  " + _format_record(record, moment, zone))
    return "\n".join(lines)


def format_history(
    records: list[OutageRecord], now: datetime, timezone_name: str
) -> str:
    if not records:
        return "No outages recorded."
    zone = zone_for(timezone_name)
    return "\n".join(_format_record(record, now, zone) for record in records)


def format_stats(title: str, buckets: list[StatBucket]) -> str:
    if not buckets:
        return f"{title}\n  none"
    lines = [title]
    current = None
    for bucket in buckets:
        if bucket.period != current:
            current = bucket.period
            lines.append(bucket.period)
        noun = "outage" if bucket.count == 1 else "outages"
        lines.append(
            f"  {bucket.type.value}: {bucket.count} {noun}, "
            f"{format_duration(bucket.duration_seconds)}"
        )
    lines.append("Charts are not implemented yet. These are counts and durations.")
    return "\n".join(lines)


def status_dict(monitor: Monitor, now: datetime) -> dict[str, object]:
    return {
        "version": __version__,
        "database": str(monitor.store.path),
        "config": None
        if monitor.config.config_path is None
        else str(monitor.config.config_path),
        "seeded": monitor.tracker.seeded,
        "paused": monitor.paused,
        "power": monitor.tracker.power.value if monitor.tracker.seeded else "unknown",
        "network": monitor.tracker.network.value if monitor.tracker.seeded else "unknown",
        "tray": monitor.tray.value,
        "battery_percent": monitor.last_power.percent,
        "battery_seconds_left": monitor.last_power.seconds_left,
        "power_note": monitor.last_power.note,
        "network_note": monitor.last_network.note,
        "open_outages": [
            record_dict(record, now) for record in monitor.store.open_records()
        ],
    }


def record_dict(record: OutageRecord, now: datetime) -> dict[str, object]:
    return {
        "id": record.id,
        "type": record.type.value,
        "started_at": record.started_at.isoformat(),
        "ended_at": None if record.ended_at is None else record.ended_at.isoformat(),
        "duration_seconds": record.duration_seconds,
        "elapsed_seconds": record.elapsed_seconds(now),
        "open": record.open,
        "source": record.source,
        "label": record.label,
        "confidence": record.confidence,
        "ground_truth": record.ground_truth,
        "detail": record.detail,
    }


def dumps(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _format_classification(result: PollResult) -> list[str]:
    classification = result.classification
    assert classification is not None
    if (
        classification.label.value == "unknown"
        and classification.leading.value != "unknown"
    ):
        headline = (
            f"classifier: unknown (confidence {classification.confidence:.2f}, "
            f"leading guess {classification.leading.value})"
        )
    else:
        headline = (
            f"classifier: {classification.label.value} "
            f"(confidence {classification.confidence:.2f})"
        )
    lines = [headline]
    parts = []
    for reading in classification.readings:
        marker = " stub" if reading.stub else ""
        parts.append(f"{reading.name}={reading.state}{marker}")
    lines.append("signals: " + ", ".join(parts))
    for note in classification.notes:
        lines.append(f"note: {note}")
    if classification.prompt:
        ids = [
            event.outage.id
            for event in result.events
            if isinstance(event, OutageStarted) and event.outage.id is not None
        ]
        lines.append(
            "prompt: stub: " + StubConfirmationPrompt.menu_text(classification, ids)
        )
    return lines


def _format_event(event: Event) -> str:
    if isinstance(event, OutageStarted):
        number = "?" if event.outage.id is None else str(event.outage.id)
        return f"opened {event.type.value} outage #{number}"
    if isinstance(event, OutageEnded):
        number = "?" if event.id is None else str(event.id)
        return (
            f"closed {event.type.value} outage #{number} "
            f"after {format_duration(event.duration_seconds)}"
        )
    return str(event)


def _format_record(record: OutageRecord, now: datetime, zone) -> str:
    start = record.started_at.astimezone(zone).isoformat(timespec="seconds")
    if record.open:
        span = f"open {format_duration(record.elapsed_seconds(now))}"
    else:
        span = f"closed {format_duration(record.duration_seconds or 0)}"
    label = record.label or "unlabeled"
    confidence = (
        "" if record.confidence is None else f" confidence={record.confidence:.2f}"
    )
    truth = "" if not record.ground_truth else f" ground-truth={record.ground_truth}"
    return (
        f"#{record.id} {record.type.value} {start} {span} "
        f"{record.source} label={label}{confidence}{truth}"
    )


def _battery_line(power: PowerReading) -> str:
    bits: list[str] = []
    if power.percent is not None:
        bits.append(f"{power.percent:.0f}%")
    if power.seconds_left is not None:
        bits.append(f"about {format_duration(power.seconds_left)} left")
    if not bits:
        return "battery: unknown"
    return "battery: " + ", ".join(bits)


def stats_dict(timezone_name: str, day: list[StatBucket], week: list[StatBucket]) -> dict:
    def encode(buckets: list[StatBucket]) -> list[dict[str, object]]:
        return [
            {
                "period": bucket.period,
                "type": bucket.type.value,
                "count": bucket.count,
                "duration_seconds": bucket.duration_seconds,
            }
            for bucket in buckets
        ]

    return {"timezone": timezone_name or "local", "day": encode(day), "week": encode(week)}
