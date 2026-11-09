Title: Tray and menu-bar UI polish

Labels: enhancement, ui, macos, windows, linux

## Description

Version 0.1 draws a colored circle and a menu with status, recent outages, pause, a stub settings item, a stub question, and quit. Offline wins over on-battery. This issue is the icon and the menu, not the one-click question (that is the confirmation-prompt issue).

Estimated effort: about 14 hours.

## Acceptance criteria

- [ ] Icons exist for normal, on battery, offline, and paused, including a macOS template image and a high-DPI size.
- [ ] The recent-outage submenu shows the latest rows, including classifier label, and updates when a new row is written.
- [ ] The status line shows power, network, and the open outage label together.
- [ ] The four colors remain distinguishable at menu-bar size.
- [ ] The icon is not redrawn when the tray state did not change.
- [ ] With no display, `brownout-buddy run` still monitors headless.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-4-tray-ui
