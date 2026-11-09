import sys
from datetime import datetime, timezone

from brownout_buddy.actions import ActionExecutor, plan_actions
from brownout_buddy.classifier.types import Classification
from brownout_buddy.config import CommandConfig, Config
from brownout_buddy.models import (
    NetworkStatus,
    OpenOutage,
    OutageLabel,
    OutageStarted,
    OutageType,
    PowerReading,
    PowerSource,
)

T0 = datetime(2026, 5, 1, tzinfo=timezone.utc)


def _power_event() -> OutageStarted:
    outage = OpenOutage(OutageType.POWER, T0)
    return OutageStarted(OutageType.POWER, T0, outage)


def test_stubs_are_labeled_and_commands_are_not_run_by_the_planner():
    config = Config(
        dim_brightness=True,
        battery_saver=True,
        pause_processes=("Dropbox", "Syncthing"),
        commands=(CommandConfig("power_loss", ("echo", "hi")),),
    )
    power = PowerReading(PowerSource.BATTERY, percent=50, seconds_left=125)
    planned = plan_actions(
        [_power_event()],
        config,
        power,
        NetworkStatus.ONLINE,
        None,
    )
    by_name = {item.name: item for item in planned}
    assert by_name["notify"].kind == "stub"
    assert "2m 5s" in by_name["notify"].message
    assert "not implemented" in by_name["notify"].message
    assert by_name["dim_brightness"].kind == "stub"
    assert by_name["battery_saver"].kind == "stub"
    assert "Dropbox" in by_name["pause_processes"].message
    assert by_name["command:power_loss"].kind == "command"
    assert by_name["command:power_loss"].argv == ("echo", "hi")


def test_executor_runs_argv_without_a_shell_and_records_stub():
    calls = []

    def runner(argv, timeout):
        calls.append((argv, timeout))
        return 0, "ok"

    planned = plan_actions(
        [_power_event()],
        Config(notify=True, commands=(CommandConfig("power_loss", (sys.executable, "-c", "print(1)")),)),
        PowerReading(PowerSource.BATTERY, seconds_left=None),
        NetworkStatus.ONLINE,
        Classification(
            label=OutageLabel.BROWNOUT,
            confidence=0.75,
            leading=OutageLabel.BROWNOUT,
            votes={},
            readings=(),
            prompt=False,
            question=None,
            notes=(),
        ),
    )
    results = ActionExecutor(runner=runner, timeout=3).execute(planned)
    statuses = {result.name: result.status for result in results}
    assert statuses["notify"] == "stub"
    assert "brownout" in next(result.message for result in results if result.name == "notify")
    assert statuses["command:power_loss"] == "ok"
    assert calls[0][0][0] == sys.executable

    failed = ActionExecutor(runner=lambda argv, timeout: (127, "missing"), timeout=1).execute(
        [item for item in planned if item.kind == "command"]
    )
    assert failed[0].status == "error"
    assert "127" in failed[0].message


def test_real_subprocess_command():
    planned = plan_actions(
        [_power_event()],
        Config(
            notify=False,
            commands=(CommandConfig("power_loss", (sys.executable, "-c", "print('pong')")),),
        ),
        PowerReading(PowerSource.BATTERY),
        NetworkStatus.ONLINE,
        None,
    )
    results = ActionExecutor(timeout=10).execute(planned)
    assert results[0].status == "ok"
    assert "pong" in results[0].message
    missing = ActionExecutor(timeout=2).execute(
        [
            type(planned[0])(
                name="command:missing",
                kind="command",
                message="",
                argv=("/no/such/brownout-buddy-bin",),
            )
        ]
    )
    assert missing[0].status == "error"
