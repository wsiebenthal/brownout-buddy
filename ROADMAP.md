# Roadmap

Hour figures are rough engineering estimates for one person who already knows the codebase. They include implementation, platform testing, and the docs or fixtures that feature needs. They are not a calendar.

**About 278 hours remain after version 0.1.** The work already in the repository is listed under "Delivered" and is not part of that total.

Paste-ready issue text for every phase lives in [docs/issues/](docs/issues/README.md).

| Phase | Left | Draft |
| --- | ---: | --- |
| [1. Per-OS power detection](#phase-1-per-os-power-detection) | 18h | [01](docs/issues/01-per-os-power-detection.md) |
| [2. Per-OS network detection](#phase-2-per-os-network-detection) | 20h | [02](docs/issues/02-per-os-network-detection.md) |
| [3. Protect-work actions](#phase-3-protect-work-actions) | 24h | [03](docs/issues/03-protect-work-actions.md) |
| [4. Tray UI](#phase-4-tray-ui) | 14h | [04](docs/issues/04-tray-ui.md) |
| [5. Settings UI](#phase-5-settings-ui) | 16h | [05](docs/issues/05-settings-ui.md) |
| [6. Outage log and charts](#phase-6-outage-log-and-charts) | 16h | [06](docs/issues/06-outage-log-and-charts.md) |
| [7. CSV export](#phase-7-csv-export) | 6h | [07](docs/issues/07-csv-export.md) |
| [8. Notifications](#phase-8-notifications) | 10h | [08](docs/issues/08-notifications.md) |
| [9. Phone hotspot fallback](#phase-9-phone-hotspot-fallback) | 14h | [09](docs/issues/09-phone-hotspot-fallback.md) |
| [10. Is it just me or my area](#phase-10-is-it-just-me-or-my-area) | 12h | [10](docs/issues/10-area-status-check.md) |
| [11. UPS and NUT integration](#phase-11-ups-and-nut-integration) | 14h | [11](docs/issues/11-ups-nut-integration.md) |
| [12. Auto-start on login](#phase-12-auto-start-on-login) | 8h | [12](docs/issues/12-autostart-on-login.md) |
| [13. Packaging and auto-update](#phase-13-packaging-and-auto-update) | 22h | [13](docs/issues/13-packaging-and-auto-update.md) |
| [14. Localization](#phase-14-localization) | 12h | [14](docs/issues/14-localization.md) |
| [15. Tests and docs](#phase-15-tests-and-docs) | 16h | [15](docs/issues/15-tests-and-docs.md) |
| [16. Ambient light signal](#phase-16-ambient-light-signal) | 16h | [16](docs/issues/16-ambient-light-signal.md) |
| [17. LAN sentinel heartbeat](#phase-17-lan-sentinel-heartbeat) | 14h | [17](docs/issues/17-lan-sentinel-heartbeat.md) |
| [18. Brownout or unplugged prompt](#phase-18-brownout-or-unplugged-prompt) | 8h | [18](docs/issues/18-confirmation-prompt.md) |
| [19. Pattern heuristics](#phase-19-pattern-heuristics) | 18h | [19](docs/issues/19-pattern-heuristics.md) |
| **Remaining** | **278h** | |

## Delivered in 0.1

This is the base the phases below sit on. It is already in the tree, so it adds no hours to the table.

- Headless and optional tray monitor, pause flag, status, history, day/week stats, CSV.
- Power source via psutil. TCP internet probes. Linux default-route heuristic. Configurable LAN probes.
- SQLite outage intervals with restart continuity. Simulator: `power-loss`, `unplug`, `offline`, `lan-down`, `restore`.
- User commands for live outages. Honest stubs for process pause, brightness, battery saver, and notifications.
- Classifier core: pluggable signals, internet-coincidence signal, ICMP gateway ping, rule score, `label` and `confidence` columns, ground-truth column, `brownout-buddy label`.
- Light capability check (no lux, no webcam). Sentinel, prompt, and pattern objects exist and do not affect the score unless a test or the simulator injects a reading.

## Phase 1: Per-OS power detection

**18 hours.** psutil polling misses events between samples and reports nothing on many desktops.

- macOS: IOKit or `pmset`, including "no battery" versus a read error (4h).
- Windows: `WM_POWERBROADCAST` and `GetSystemPowerStatus`, so a sleep/wake does not look like a new outage (5h).
- Linux: UPower on D-Bus in addition to sysfs, and a clear result when the seat has no battery (5h).
- Shared tests for lid close, sudden unplug, and the unknown state the tracker already ignores (4h).

## Phase 2: Per-OS network detection

**20 hours.** Version 0.1 already pings the default gateway for the classifier and uses TCP for internet targets. This phase hardens the LAN-versus-upstream split.

- Default gateway and default route on macOS and Windows, not only Linux `/proc/net/route` (4h).
- Captive portals and DNS-only failure must not be stored as an ISP outage (5h).
- Probe policy: IP literals first, hostname probes optional, stop early when one internet target answers (4h).
- Windows Network List Manager and macOS reachability as a second opinion next to the ping (4h).
- Document and test the UPS caveat: a gateway that stays up is not proof of an unplug (3h).

## Phase 3: Protect-work actions

**24 hours.** Commands already run. These are the OS actions that are stubs today.

- Pause and resume a named set of sync apps (Dropbox, OneDrive, Google Drive, Syncthing) per OS, and put them back when power returns (8h).
- Lower brightness on outage and restore the previous level (4h).
- Battery saver: Windows `powercfg`, macOS `pmset`, Linux power-profiles daemon (5h).
- Timeouts, a visible failure when a command exits non-zero, and no shell interpolation (4h).
- One rollback path so a restore undoes only what this outage changed (3h).

## Phase 4: Tray UI

**14 hours.** A colored circle and a basic menu exist. The question in the menu is phase 18, not this one.

- Template and high-DPI icons, including a macOS menu-bar image that follows the bar color (4h).
- Recent-outage submenu that updates without rebuilding the whole icon (3h).
- Status line that shows power, network, and the open classifier label together (3h).
- Contrast of the four states (normal, battery, offline, paused) at small sizes (2h).
- Do not flicker the icon on every poll when the state did not change (2h).

## Phase 5: Settings UI

**16 hours.** Today the settings item tells you to edit TOML.

- A local window, not a web view that phones home, for the existing config keys (6h).
- Editors for probes, commands, and the sentinel host, with the same validation as the TOML loader (6h).
- Save, revert, and "open the example file" without destroying a comment the user wrote (4h).

## Phase 6: Outage log and charts

**16 hours.** Rows, day/week totals, and CSV already exist. This phase is the part you look at.

- Local chart of outage minutes by day and week, drawn without a network call (6h).
- Keep an in-progress outage visible and let the user delete a row the simulator or a glitch created (4h).
- Retention: drop or archive rows older than a configured age (3h).
- Show classifier label, confidence, and ground truth on the same view (3h).

## Phase 7: CSV export

**6 hours.** A full-table export already works.

- Filters for type, label, and a date range (4h).
- Time zone choice and a stable column set so a spreadsheet opened next month still lines up (2h).

## Phase 8: Notifications

**10 hours.** The monitor already builds the sentence, including a battery estimate and the classifier label, and then marks it as a stub.

- Native notification on macOS, Windows, and Linux, with the same sentence (5h).
- Quiet hours, a minimum gap so a flap does not notify every poll, and no notification while paused (5h).

## Phase 9: Phone hotspot fallback

**14 hours.**

- Remember one or two phone SSIDs the user marks as "this is my hotspot" (4h).
- Per-OS help to join that network when upstream dies and the phone is the intended path (6h).
- Do not log a new outage for the few seconds between Wi-Fi networks (4h).

## Phase 10: Is it just me or my area

**12 hours.** Opt-in only. The privacy section of the README has to name the request before this ships.

- Fetch a configured public status page (for example an ISP or a utility outage page) with a short timeout (6h).
- Cache the answer, and label it as someone else's page rather than a measurement (3h).
- Show "area report" next to the local classifier label in the menu (3h).

## Phase 11: UPS and NUT integration

**14 hours.** This is the other half of the gateway-UPS caveat: the laptop may still be on a UPS while the wall is dead, or the router may be the device on the UPS.

- Read NUT (`upsc`) for on-line versus on-battery (5h).
- If the wall is out and the laptop is still on a UPS, record a brownout without waiting for the laptop battery (5h).
- Config for the NUT host, and a stub-free error when `upsc` is not installed (4h).

## Phase 12: Auto-start on login

**8 hours.**

- macOS Launch Agent (3h).
- Windows startup entry for the current user (3h).
- Linux XDG autostart (2h).

## Phase 13: Packaging and auto-update

**22 hours.**

- One-folder builds for the three desktops (8h).
- Signed installers where the platform requires a signature to run (6h).
- An update check the user turns on, with the privacy note updated in the same change (8h).

## Phase 14: Localization

**12 hours.** English remains the source language.

- Pull user-visible strings into a catalog (3h).
- Tagalog translation (3h).
- Cebuano translation (2h).
- A test that every catalog key exists in each language, and a way to switch locale without a reinstall (4h).

## Phase 15: Tests and docs

**16 hours.** Unit tests for the pure logic ship with 0.1. What is missing is confidence on real operating systems.

- Fixtures or virtual machines for one sleep/wake and one unplug on each OS (8h).
- A troubleshooting page for false ISP outages, captive portals, and a router on a UPS (5h).
- Keep the issue drafts in `docs/issues/` in sync when a phase shrinks (3h).

## Phase 16: Ambient light signal

**16 hours.** Version 0.1 only answers "does a sensor seem to exist?" Live lux must not be faked, and the webcam stays out of scope on every platform.

- Windows: call `Windows.Devices.Sensors.LightSensor` when the capability check says it is present, and skip the signal when it is not (6h).
- Linux: read IIO illuminance and decide "dropped" against the level just before AC loss (5h).
- macOS: keep the unsupported stub unless a documented API shows up; write down the decision either way (3h).
- Tests on a machine with a sensor and a machine without one, both of which must still classify (2h).

A light drop votes with a brownout. A steady reading votes with an unplug. A missing sensor adds no points, which is the behavior of the stub today.

## Phase 17: LAN sentinel heartbeat

**14 hours.** The config host is stored and is not contacted today. `--sentinel-silent` only exists so the scorer can be tested.

- A small heartbeat a phone or a smart plug can send, and a timeout that means "silent" (6h).
- Discovery or a manual host, plus a clear error when the device was never seen (4h).
- Fuse silence into the brownout vote, and do not treat a phone that went to sleep as a brownout by itself (4h).

## Phase 18: Brownout or unplugged prompt

**8 hours.** `brownout-buddy label <id> <answer>` already writes ground truth and leaves the model label in place. The tray item only prints instructions.

- One click: Brownout, Unplugged, or Not sure, shown only when the stored sample asked the question (4h).
- Write that click through `set_ground_truth` and stop asking about that outage (2h).
- Ask on the menu thread without blocking the monitor, and do not ask again after the outage closes (2h).

## Phase 19: Pattern heuristics

**18 hours.** `PatternSignal.read` accepts history and returns a stub. Ground truth from phase 18 is the training material. A pattern must not outvote a gateway that is clearly up or clearly down.

- Time-of-day rates from rows whose ground truth says unplugged versus brownout (8h).
- Clustering: several outages in the same evening count differently from a single unplug at a usual time (6h).
- A pattern reading the scorer already knows how to ignore until this phase turns `stub` off, with a cap so it only moves low-confidence calls (4h).
