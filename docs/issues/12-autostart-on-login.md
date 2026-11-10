Title: Auto-start on login

Labels: enhancement, packaging, macos, windows, linux

## Description

The monitor only runs when someone starts it. A brownout that happens before launch is invisible, which the baseline rule already admits. Starting at login is the practical fix. It should be the current user, not a system service, and it should be removable.

Estimated effort: about 8 hours.

## Acceptance criteria

- [ ] macOS: a per-user Launch Agent starts `brownout-buddy run` at login and can be unloaded.
- [ ] Windows: a per-user startup entry does the same and can be removed.
- [ ] Linux: an XDG autostart entry does the same and can be removed.
- [ ] Install and uninstall are commands, and neither requires root.
- [ ] The README tells the user the file path that was written.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-12-auto-start-on-login
