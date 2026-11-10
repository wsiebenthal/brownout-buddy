"""Protect-work actions.

User commands whose argv is configured actually run, without a shell.
Pausing sync apps, dimming the screen, turning on battery saver, and
native notifications are stubs: the monitor records that it did not do
them. The simulator does not call :class:`ActionExecutor`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from brownout_buddy.classifier.types import Classification
from brownout_buddy.config import Config
from brownout_buddy.models import NetworkStatus, OutageEnded, OutageStarted, OutageType, PowerReading
from brownout_buddy.tracking import Event


@dataclass(frozen=True)
class PlannedAction:
    name: str
    kind: str  # "stub" or "command"
    message: str
    argv: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionResult:
    name: str
    status: str  # stub, ok, error
    message: str


def plan_actions(
    events: list[Event],
    config: Config,
    power: PowerReading,
    network_after: NetworkStatus,
    classification: Classification | None,
) -> list[PlannedAction]:
    triggers = _triggers(events, network_after)
    planned: list[PlannedAction] = []
    if "power_loss" in triggers:
        if config.notify:
            planned.append(
                PlannedAction(
                    name="notify",
                    kind="stub",
                    message=_power_message(power, classification),
                )
            )
        if config.dim_brightness:
            planned.append(
                PlannedAction(
                    name="dim_brightness",
                    kind="stub",
                    message="Screen brightness was not changed. Brightness control is not implemented yet.",
                )
            )
        if config.battery_saver:
            planned.append(
                PlannedAction(
                    name="battery_saver",
                    kind="stub",
                    message="OS battery saver was not enabled. That action is not implemented yet.",
                )
            )
        if config.pause_processes:
            names = ", ".join(config.pause_processes)
            planned.append(
                PlannedAction(
                    name="pause_processes",
                    kind="stub",
                    message=(
                        f"Not pausing {names}. Pausing sync apps is not implemented yet."
                    ),
                )
            )
    elif config.notify and any(
        name in triggers for name in ("internet_down", "lan_down")
    ):
        kind = "Internet" if "internet_down" in triggers else "LAN or router"
        extra = ""
        if classification is not None:
            extra = (
                f" Classifier: {classification.label.value} "
                f"({classification.confidence:.2f})."
            )
        planned.append(
            PlannedAction(
                name="notify",
                kind="stub",
                message=(
                    f"{kind} looks down.{extra} Native notifications are not "
                    "implemented yet; this message is only in the local log."
                ),
            )
        )
    for trigger in triggers:
        if config.notify and trigger in {"power_restore", "connectivity_restore"}:
            planned.append(
                PlannedAction(
                    name="notify",
                    kind="stub",
                    message=(
                        f"{trigger.replace('_', ' ')} detected. Native notifications "
                        "are not implemented yet; this message is only in the local log."
                    ),
                )
            )
        for command in config.commands:
            if command.on == trigger:
                planned.append(
                    PlannedAction(
                        name=f"command:{trigger}",
                        kind="command",
                        message=" ".join(command.argv),
                        argv=command.argv,
                    )
                )
    return planned


class ActionExecutor:
    def __init__(self, runner=None, timeout: float = 30):
        self._runner = runner or run_command
        self._timeout = timeout

    def execute(self, planned: list[PlannedAction]) -> list[ActionResult]:
        results: list[ActionResult] = []
        for action in planned:
            if action.kind == "stub":
                results.append(
                    ActionResult(name=action.name, status="stub", message=action.message)
                )
                continue
            code, output = self._runner(list(action.argv), self._timeout)
            if code == 0:
                message = output or "command finished"
                results.append(ActionResult(action.name, "ok", message))
            else:
                detail = output or "command failed"
                results.append(
                    ActionResult(action.name, "error", f"exit {code}: {detail}")
                )
        return results


def run_command(argv: list[str], timeout: float) -> tuple[int, str]:
    """Run ``argv`` with no shell. Returns ``(exit_code, clipped_output)``."""

    try:
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            timeout=timeout,
            check=False,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        return 124, _clip(exc.stdout, exc.stderr) or "command timed out"
    except OSError as exc:
        return 127, str(exc)
    return completed.returncode, _clip(completed.stdout, completed.stderr)


def _triggers(events: list[Event], network_after: NetworkStatus) -> list[str]:
    names: list[str] = []
    for event in events:
        if isinstance(event, OutageStarted):
            if event.type == OutageType.POWER:
                names.append("power_loss")
            elif event.type == OutageType.INTERNET:
                names.append("internet_down")
            elif event.type == OutageType.LAN:
                names.append("lan_down")
        elif isinstance(event, OutageEnded):
            if event.type == OutageType.POWER:
                names.append("power_restore")
            elif (
                event.type in (OutageType.INTERNET, OutageType.LAN)
                and network_after == NetworkStatus.ONLINE
            ):
                names.append("connectivity_restore")
    return names


def _power_message(power: PowerReading, classification: Classification | None) -> str:
    if power.seconds_left is None:
        estimate = "Battery time remaining is unavailable."
    else:
        estimate = f"About {format_duration(power.seconds_left)} of battery left."
    label = ""
    if classification is not None:
        label = (
            f" Classifier: {classification.label.value} "
            f"({classification.confidence:.2f})."
        )
    return (
        f"Power lost. {estimate}{label} Native notifications are not implemented "
        "yet; this message is only in the local log."
    )


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _clip(*parts: object) -> str:
    chunks: list[str] = []
    for part in parts:
        if not part:
            continue
        if isinstance(part, bytes):
            text = part.decode("utf-8", "replace")
        else:
            text = str(part)
        text = text.strip()
        if text:
            chunks.append(text)
    return "\n".join(chunks)[:500]
