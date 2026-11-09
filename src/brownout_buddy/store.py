"""SQLite outage log.

The database lives only on the machine running Brownout Buddy. One file
holds open and finished outages plus the last monitor snapshot so a restart
continues an open interval instead of opening a second one.

Timestamps are ISO-8601 with a UTC offset. ``duration_seconds`` is empty
while an outage is still open; stats add time up to ``now`` for those rows.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from brownout_buddy.models import (
    NetworkStatus,
    OpenOutage,
    OutageEnded,
    OutageLabel,
    OutageRecord,
    OutageStarted,
    OutageType,
    PowerReading,
    PowerSource,
)
from brownout_buddy.tracking import Debouncer, Event, Tracker

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outages (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_seconds INTEGER,
    source TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '{}',
    label TEXT CHECK (
        label IS NULL OR label IN ('brownout', 'unplugged', 'isp-outage', 'unknown')
    ),
    confidence REAL CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
    ),
    ground_truth TEXT CHECK (
        ground_truth IS NULL OR ground_truth IN (
            'brownout', 'unplugged', 'isp-outage', 'unknown'
        )
    ),
    signals TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS monitor_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    seeded INTEGER NOT NULL,
    power TEXT NOT NULL,
    network TEXT NOT NULL,
    paused INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    battery_percent REAL,
    battery_seconds_left INTEGER,
    network_note TEXT NOT NULL DEFAULT '',
    power_note TEXT NOT NULL DEFAULT '',
    debounce_pending TEXT,
    debounce_count INTEGER NOT NULL DEFAULT 0,
    debounce_seeded INTEGER NOT NULL DEFAULT 0,
    debounce_stable TEXT NOT NULL DEFAULT 'unknown'
);

CREATE INDEX IF NOT EXISTS idx_outages_started ON outages (started_at);
"""


@dataclass
class Snapshot:
    tracker: Tracker
    debouncer: Debouncer
    paused: bool
    updated_at: datetime | None
    battery_percent: float | None
    battery_seconds_left: int | None
    network_note: str
    power_note: str


class StoreError(Exception):
    """The local log could not complete a read or write."""


@dataclass(frozen=True)
class StatBucket:
    period: str
    type: OutageType
    count: int
    duration_seconds: int


class OutageStore:
    def __init__(self, path: Path):
        self.path = path
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1')"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def load(self, debouncer: Debouncer) -> Snapshot | None:
        row = self._conn.execute("SELECT * FROM monitor_state WHERE id = 1").fetchone()
        if row is None or not row["seeded"]:
            return None
        tracker = Tracker(
            power=PowerSource(row["power"]),
            network=NetworkStatus(row["network"]),
            seeded=True,
        )
        for record in self._open_rows():
            tracker.open_outages[record.type] = OpenOutage(
                type=record.type,
                started_at=record.started_at,
                id=record.id,
            )
        debouncer.stable = NetworkStatus(row["debounce_stable"])
        pending = row["debounce_pending"]
        debouncer.pending = NetworkStatus(pending) if pending else None
        debouncer.count = int(row["debounce_count"])
        debouncer.seeded = bool(row["debounce_seeded"])
        return Snapshot(
            tracker=tracker,
            debouncer=debouncer,
            paused=bool(row["paused"]),
            updated_at=_parse_dt(row["updated_at"]),
            battery_percent=row["battery_percent"],
            battery_seconds_left=row["battery_seconds_left"],
            network_note=row["network_note"],
            power_note=row["power_note"],
        )

    def persist(
        self,
        tracker: Tracker,
        debouncer: Debouncer,
        events: list[Event],
        *,
        paused: bool,
        updated_at: datetime,
        power: PowerReading,
        network_note: str,
        source: str,
        detail: dict[str, object],
        classification: dict[str, object] | None = None,
    ) -> None:
        """Write transitions and the snapshot in one transaction.

        ``classification`` is stamped onto every outage opened by this
        sample. ``None`` leaves the label columns empty (classifier off,
        or nothing new opened).
        """

        label, confidence, signals_json = _classification_columns(classification)
        try:
            for event in events:
                if isinstance(event, OutageStarted):
                    cursor = self._conn.execute(
                        """
                        INSERT INTO outages (
                            type, started_at, ended_at, duration_seconds, source,
                            detail, label, confidence, ground_truth, signals
                        ) VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, NULL, ?)
                        """,
                        (
                            event.type.value,
                            _format_dt(event.started_at),
                            source,
                            json.dumps(detail, sort_keys=True),
                            label,
                            confidence,
                            signals_json,
                        ),
                    )
                    tracker.set_open_id(event.type, int(cursor.lastrowid))
                elif isinstance(event, OutageEnded):
                    if event.id is None:
                        raise StoreError(
                            "cannot close an outage that was never stored"
                        )
                    cursor = self._conn.execute(
                        """
                        UPDATE outages
                        SET ended_at = ?, duration_seconds = ?
                        WHERE id = ?
                        """,
                        (
                            _format_dt(event.ended_at),
                            event.duration_seconds,
                            event.id,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise StoreError(f"no outage with id {event.id}")
            self._write_snapshot(
                tracker,
                debouncer,
                paused=paused,
                updated_at=updated_at,
                power=power,
                network_note=network_note,
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def set_paused(self, paused: bool, updated_at: datetime) -> None:
        current = self._conn.execute(
            "SELECT id FROM monitor_state WHERE id = 1"
        ).fetchone()
        if current is None:
            self._conn.execute(
                """
                INSERT INTO monitor_state (
                    id, seeded, power, network, paused, updated_at
                ) VALUES (1, 0, 'ac', 'online', ?, ?)
                """,
                (int(paused), _format_dt(updated_at)),
            )
        else:
            self._conn.execute(
                "UPDATE monitor_state SET paused = ?, updated_at = ? WHERE id = 1",
                (int(paused), _format_dt(updated_at)),
            )
        self._conn.commit()

    def is_paused(self) -> bool:
        row = self._conn.execute(
            "SELECT paused FROM monitor_state WHERE id = 1"
        ).fetchone()
        return bool(row["paused"]) if row else False

    def get(self, outage_id: int) -> OutageRecord | None:
        row = self._conn.execute(
            "SELECT * FROM outages WHERE id = ?", (outage_id,)
        ).fetchone()
        return _record(row) if row else None

    def set_ground_truth(self, outage_id: int, label: str) -> OutageRecord:
        """Store a person's answer without changing the model label.

        The tray question that would collect this in one click is not built
        yet. This method is what that click will call.
        """

        try:
            OutageLabel(label)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in OutageLabel)
            raise StoreError(f"ground truth must be one of: {allowed}.") from exc
        existing = self.get(outage_id)
        if existing is None:
            raise StoreError(f"no outage with id {outage_id}")
        signals = dict(existing.signals)
        signals["prompt"] = False
        signals["ground_truth"] = label
        self._conn.execute(
            """
            UPDATE outages
            SET ground_truth = ?, signals = ?
            WHERE id = ?
            """,
            (label, json.dumps(signals, sort_keys=True), outage_id),
        )
        self._conn.commit()
        updated = self.get(outage_id)
        if updated is None:  # pragma: no cover - row was just updated
            raise StoreError(f"no outage with id {outage_id}")
        return updated

    def open_records(self) -> list[OutageRecord]:
        return self._open_rows()

    def recent(
        self,
        *,
        limit: int = 20,
        outage_type: OutageType | None = None,
        label: str | None = None,
    ) -> list[OutageRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if outage_type is not None:
            clauses.append("type = ?")
            params.append(outage_type.value)
        if label is not None:
            clauses.append("label = ?")
            params.append(label)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = self._conn.execute(
            f"""
            SELECT * FROM outages
            {where}
            ORDER BY started_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [_record(row) for row in rows]

    def stats(
        self, *, by: str, tz, now: datetime
    ) -> list[StatBucket]:
        if by not in ("day", "week"):
            raise ValueError("by must be 'day' or 'week'")
        buckets: dict[tuple[str, OutageType], list[int]] = defaultdict(
            lambda: [0, 0]
        )
        for record in self._all_rows():
            local = record.started_at.astimezone(tz)
            if by == "day":
                key = local.date().isoformat()
            else:
                year, week, _ = local.isocalendar()
                key = f"{year}-W{week:02d}"
            duration = record.elapsed_seconds(now)
            slot = buckets[(key, record.type)]
            slot[0] += 1
            slot[1] += duration
        return [
            StatBucket(period=period, type=outage_type, count=count, duration_seconds=total)
            for (period, outage_type), (count, total) in sorted(
                buckets.items(), key=lambda item: (item[0][0], item[0][1].value)
            )
        ]

    def export_csv(self, destination: Path) -> int:
        rows = self._all_rows()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "id",
                    "type",
                    "started_at",
                    "ended_at",
                    "duration_seconds",
                    "open",
                    "source",
                    "label",
                    "confidence",
                    "ground_truth",
                    "detail",
                ]
            )
            for record in rows:
                writer.writerow(
                    [
                        record.id,
                        record.type.value,
                        _format_dt(record.started_at),
                        "" if record.ended_at is None else _format_dt(record.ended_at),
                        ""
                        if record.duration_seconds is None
                        else record.duration_seconds,
                        "true" if record.open else "false",
                        record.source,
                        record.label or "",
                        "" if record.confidence is None else record.confidence,
                        record.ground_truth or "",
                        json.dumps(record.detail, sort_keys=True),
                    ]
                )
        return len(rows)

    def _write_snapshot(
        self,
        tracker: Tracker,
        debouncer: Debouncer,
        *,
        paused: bool,
        updated_at: datetime,
        power: PowerReading,
        network_note: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO monitor_state (
                id, seeded, power, network, paused, updated_at,
                battery_percent, battery_seconds_left, network_note, power_note,
                debounce_pending, debounce_count, debounce_seeded, debounce_stable
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                seeded = excluded.seeded,
                power = excluded.power,
                network = excluded.network,
                paused = excluded.paused,
                updated_at = excluded.updated_at,
                battery_percent = excluded.battery_percent,
                battery_seconds_left = excluded.battery_seconds_left,
                network_note = excluded.network_note,
                power_note = excluded.power_note,
                debounce_pending = excluded.debounce_pending,
                debounce_count = excluded.debounce_count,
                debounce_seeded = excluded.debounce_seeded,
                debounce_stable = excluded.debounce_stable
            """,
            (
                int(tracker.seeded),
                tracker.power.value,
                tracker.network.value,
                int(paused),
                _format_dt(updated_at),
                power.percent,
                power.seconds_left,
                network_note,
                power.note,
                None if debouncer.pending is None else debouncer.pending.value,
                debouncer.count,
                int(debouncer.seeded),
                debouncer.stable.value,
            ),
        )

    def _open_rows(self) -> list[OutageRecord]:
        rows = self._conn.execute(
            "SELECT * FROM outages WHERE ended_at IS NULL ORDER BY id"
        ).fetchall()
        return [_record(row) for row in rows]

    def _all_rows(self) -> list[OutageRecord]:
        rows = self._conn.execute(
            "SELECT * FROM outages ORDER BY started_at, id"
        ).fetchall()
        return [_record(row) for row in rows]


def _record(row: sqlite3.Row) -> OutageRecord:
    raw_detail = row["detail"] or "{}"
    try:
        detail = json.loads(raw_detail)
    except json.JSONDecodeError:
        detail = {"raw": raw_detail}
    if not isinstance(detail, dict):
        detail = {"value": detail}
    signals = _object_json(row["signals"] if "signals" in row.keys() else "{}")
    return OutageRecord(
        id=int(row["id"]),
        type=OutageType(row["type"]),
        started_at=_parse_dt(row["started_at"]),
        ended_at=_parse_dt(row["ended_at"]) if row["ended_at"] else None,
        duration_seconds=row["duration_seconds"],
        source=row["source"],
        detail=detail,
        label=row["label"],
        confidence=row["confidence"],
        ground_truth=row["ground_truth"],
        signals=signals,
    )


def _object_json(raw: str | None) -> dict[str, object]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _classification_columns(
    classification: dict[str, object] | None,
) -> tuple[str | None, float | None, str]:
    if not classification:
        return None, None, "{}"
    label = classification.get("label")
    confidence = classification.get("confidence")
    if label is not None:
        label = str(label)
    if confidence is not None:
        confidence = float(confidence)
    return label, confidence, json.dumps(classification, sort_keys=True)


def _format_dt(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("refusing to store a naive timestamp")
    return value.astimezone(timezone.utc).isoformat()


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def iter_stats_text(buckets: Iterable[StatBucket]) -> list[str]:
    """Group stat rows for the text UI. Kept here so the CLI stays thin."""

    lines: list[str] = []
    current = None
    for bucket in buckets:
        if bucket.period != current:
            current = bucket.period
            lines.append(bucket.period)
        lines.append(
            f"  {bucket.type.value}: {bucket.count} "
            f"outage{'s' if bucket.count != 1 else ''}, "
            f"{bucket.duration_seconds}s"
        )
    return lines
