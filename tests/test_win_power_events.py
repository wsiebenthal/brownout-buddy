from brownout_buddy.detection.win_power_events import (
    PBT_APMPOWERSTATUSCHANGE,
    PBT_APMRESUMEAUTOMATIC,
    PBT_APMRESUMESUSPEND,
    PBT_APMSUSPEND,
    PBT_POWERSETTINGCHANGE,
    PowerEvent,
    decode_power_broadcast,
)


def test_decode_ac_line_change():
    assert decode_power_broadcast(PBT_APMPOWERSTATUSCHANGE) is PowerEvent.STATUS_CHANGE


def test_decode_sleep_and_both_wake_codes():
    assert decode_power_broadcast(PBT_APMSUSPEND) is PowerEvent.SUSPEND
    assert decode_power_broadcast(PBT_APMRESUMESUSPEND) is PowerEvent.RESUME
    assert decode_power_broadcast(PBT_APMRESUMEAUTOMATIC) is PowerEvent.RESUME


def test_decode_power_setting_change():
    assert decode_power_broadcast(PBT_POWERSETTINGCHANGE) is PowerEvent.SETTING_CHANGE


def test_decode_ignores_retired_apm_codes():
    # PBT_APMBATTERYLOW (0x9) and PBT_APMQUERYSUSPEND (0x0) are no longer sent.
    assert decode_power_broadcast(0x0009) is None
    assert decode_power_broadcast(0x0000) is None