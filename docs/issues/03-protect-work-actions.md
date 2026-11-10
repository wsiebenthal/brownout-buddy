Title: Protect-work actions per OS

Labels: enhancement, actions, macos, windows, linux

## Description

Configured `argv` commands already run, without a shell, on live outages. Pausing sync apps, dimming the screen, and enabling battery saver return `status=stub` and do not touch the OS. The simulator must keep refusing to run commands.

Estimated effort: about 24 hours.

## Acceptance criteria

- [ ] A configured list of sync apps is paused on power loss and resumed on power restore, per OS, for at least one real client and a documented method for the others.
- [ ] Brightness is lowered on outage and restored to the previous value afterward.
- [ ] Battery saver maps to `powercfg` on Windows, `pmset` on macOS, and power-profiles on Linux, each with a clear error when the tool is missing.
- [ ] A non-zero command exit is stored as `error` and does not crash the monitor.
- [ ] No action is invoked with `shell=True`.
- [ ] `brownout-buddy simulate` still does not run commands or OS hooks.
- [ ] Restore undoes only the changes this outage made.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-3-protect-work-actions
