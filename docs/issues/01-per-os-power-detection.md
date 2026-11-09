Title: Per-OS power detection

Labels: enhancement, detection, macos, windows, linux

## Description

Version 0.1 polls `psutil.sensors_battery()` on a timer. That misses transitions between polls and returns "no battery" on many desktops and VMs. The tracker already ignores `unknown` and only opens a power outage on a seen AC-to-battery change. This issue replaces the poll with a native source per OS without changing that rule.

Estimated effort: about 18 hours. See the roadmap section linked below.

## Acceptance criteria

- [ ] macOS reports AC, battery, or no-battery from IOKit or `pmset`, and a read error is `unknown` rather than a fake outage.
- [ ] Windows subscribes to `WM_POWERBROADCAST` (with `GetSystemPowerStatus` as the snapshot) and does not log a new outage across sleep or wake.
- [ ] Linux reads UPower when it is available and still works from sysfs when it is not.
- [ ] A machine with no battery stays `unknown` and the log stays empty.
- [ ] Existing tracker tests still pass, and new fixtures cover unplug, replug, and lid close.
- [ ] The README power row describes the native backends instead of "psutil only".

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-1-per-os-power-detection
