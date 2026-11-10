# Brownout Buddy

[![CI](https://github.com/wsiebenthal/brownout-buddy/actions/workflows/ci.yml/badge.svg)](https://github.com/wsiebenthal/brownout-buddy/actions/workflows/ci.yml)

Brownout Buddy is a menu-bar app (a system tray on Windows and Linux) for people whose power or internet drops often enough to interrupt real work. It notices when a laptop leaves AC power and when connectivity fails, writes each outage to a database on that computer, and tries to tell a building-wide brownout apart from a cable that was simply unplugged.

Version 0.1 is a working local monitor plus a rule-based classifier. It is not a finished desktop product. Platform features that are not built yet are marked as stubs in the log and in the [roadmap](ROADMAP.md).

## Who it is for

- People who lose mains power often enough that "save your work" has to be a habit, including many households in the Philippines.
- Anyone on a laptop who wants a local record of power cuts and internet cuts: when they started, how long they lasted, and whether the router went down too.
- Not a utility for servers, and not a remote monitoring service. There is no account and no cloud.

## What works in 0.1

| Capability | Status |
| --- | --- |
| Poll AC versus battery with psutil | Works where the OS exposes a battery. A desktop or VM with no battery stays `unknown` and is not treated as an outage. |
| TCP probes for internet, plus LAN versus upstream when a route or LAN probe can say so | Works. Linux can read `/proc/net/route`. Other systems need `lan_probes` to separate a dead router from a dead ISP. |
| Menu-bar / tray icon for normal, on battery, offline, and paused | Works when a graphical session, Pillow, and a pystray backend are available. Otherwise the monitor runs in the terminal. |
| Tray menu: status, recent outages, pause, settings, quit | Pause and quit work. Settings and the "Brownout or unplugged?" item are stubs. |
| SQLite log of start, end, duration, and type | Works. The file stays on this computer. |
| Day and week counts, and CSV export | Works. Charts are not implemented. |
| Simulator | Works without a real outage, a display, or a ping. |
| User commands from config | Works for live outages. `argv` only, no shell. The simulator does not run them. |
| Classifier: brownout / unplugged / isp-outage / unknown, with a confidence score | Works from internet coincidence and a gateway ping, plus any signal the simulator injects. |
| Pause sync apps, brightness, battery saver, native notifications | Stub. The log says they were not performed. |
| Ambient light, LAN sentinel, one-click prompt, pattern learning | Stub interfaces. Live reads do not change the score. The webcam is never used. |

## Outage classifier

A new power or connectivity outage is labeled before it is stored.

| Label | Rule of thumb |
| --- | --- |
| `brownout` | AC power disappeared and the network disappeared with it. A gateway that stops answering is the strongest live clue that the router lost power too. |
| `unplugged` | AC power disappeared but the internet stayed up and the gateway still answers. |
| `isp-outage` | The computer is still on mains power, the gateway answers, and the internet probes fail. |
| `unknown` | The winning score is under 0.55, or it does not lead the next guess by 0.15. The leading guess is kept in the log. |

Confidence is capped at 0.95. These rules are not certain. When AC was lost and confidence is at or below 0.60, the record is marked so a future tray question can ask **"Brownout or unplugged?"** Version 0.1 prints that question and tells you the command that saves an answer. It does not draw the one-click prompt.

```bash
brownout-buddy label 4 unplugged
```

That stores `unplugged` as ground truth. The classifier's own label and confidence stay on the row so a later habit model can compare them.

Signals:

1. **Internet coincidence (live).** Did connectivity fail in the same sample that switched the laptop from AC to battery?
2. **Gateway ping (live).** Brownout Buddy pings the default gateway (ICMP, one echo). A missing `ping` binary is "unknown", not "router down". TCP probes are still used for internet targets, because many routers refuse TCP and that would look like a false outage.
3. **Ambient light (stub).** The app checks whether a sensor exists: Linux IIO `in_illuminance_*`, a named Windows `Windows.Devices.Sensors.LightSensor` API that is not called yet, and an explicit "unsupported" result on macOS because no documented API is used. Lux is not read. **The webcam is never opened.** `--light-drop` injects a drop so the rule can be tested.
4. **LAN sentinel (stub).** An optional always-powered device (a smart plug, or a phone left on a charger) can be named in config. Version 0.1 does not contact it. `--sentinel-silent` injects silence for tests.
5. **Tray prompt (stub).** The menu item explains the command above. It does not collect the click.
6. **Patterns (stub).** The signal accepts recent history and ignores it. Time-of-day unplug habits and outage clustering are not scored.

**A router on a UPS removes signal 2.** The gateway keeps answering through a real brownout, so a live ping cannot by itself prove the laptop was only unplugged. The log repeats that caveat whenever AC was lost and the gateway answered.

Weights, as points out of 100, live in `src/brownout_buddy/classifier/score.py`. Short version: gateway down with AC loss is +40 toward brownout, internet dying in the same sample is +35, gateway up with AC loss is +45 toward unplugged, internet still up is +35, and internet down with the gateway up and mains still present is +70 toward an ISP outage. Injected light and sentinel readings add a smaller vote. Stub readings add nothing.

## Architecture

```text
psutil battery          TCP internet probes         simulator
Linux default route     ICMP ping of the gateway    injected light / sentinel
        |                        |                          |
        v                        v                          v
   pure classifiers (power, LAN vs upstream, signal readings)
        |
        v
   network debouncer (live polls only) ---- outage tracker
        |                                        |
        v                                        v
   rule scorer (label + confidence)         SQLite outages
        |                                        |
        +------------------+---------------------+
                           v
              tray icon, or a headless terminal
                           |
                           v
        protect-work actions (commands run; OS hooks stubbed)
```

The tracker opens a power outage only when it sees AC become battery. The first live sample is a baseline: an outage already in progress is not back-filled. `unknown` battery or network readings do not open or close anything. Network changes wait for `failure_threshold` polls (default 2) so one dropped probe is not an outage. Recovery uses `recovery_threshold` (default 1). The simulator bypasses that wait and never pings.

## Tech stack

Python 3.11 or newer, on purpose. A menu-bar utility that reads a battery, pings a gateway, and writes SQLite does not need a browser runtime.

- **psutil** for the battery.
- **stdlib** `sqlite3`, `tomllib`, `socket`, `subprocess`, and `zoneinfo` for the log, config, TCP probes, ping, and stats time zones.
- **pystray** and **Pillow**, optional extra `tray`, for the icon. CI does not need a display.
- **pytest** for the state machine, the scorer, and the log.

Native power events, native reachability APIs, installers, and a settings window are later milestones. See [ROADMAP.md](ROADMAP.md).

## Install and run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# optional icon:
pip install -e ".[tray]"

brownout-buddy init-config
brownout-buddy run --headless          # terminal monitor
brownout-buddy run                     # tray when a desktop session exists
brownout-buddy status
brownout-buddy history
brownout-buddy stats --since 2026-01-01
brownout-buddy export outages.csv
```

Config is read from `--config`, then `BROWNOUT_BUDDY_CONFIG`, then `./brownout-buddy.toml` if that file exists, then the per-user file from `init-config`, otherwise built-in defaults. The database is `--db`, then `BROWNOUT_BUDDY_DB`, then `store.path`, otherwise:

| OS | Config | Database |
| --- | --- | --- |
| Linux | `$XDG_CONFIG_HOME/brownout-buddy/config.toml` or `~/.config/brownout-buddy/config.toml` | `$XDG_DATA_HOME/brownout-buddy/outages.sqlite` or `~/.local/share/brownout-buddy/outages.sqlite` |
| macOS | `~/Library/Application Support/BrownoutBuddy/config.toml` | `~/Library/Application Support/BrownoutBuddy/outages.sqlite` |
| Windows | `%APPDATA%\BrownoutBuddy\config.toml` | `%LOCALAPPDATA%\BrownoutBuddy\outages.sqlite` |

`brownout-buddy pause` and `resume` set a flag the running monitor reads on its next poll. While paused, outages that start or end are missed. Quit from the tray menu, or Ctrl-C in the terminal.

## Try it without a real outage

The simulator writes through the same tracker, scorer, and SQLite file as a live poll. It does not run your configured commands and it does not ping.

```bash
# Building lost power, and the router stopped answering. Light drop is injected.
brownout-buddy --db /tmp/demo.sqlite simulate power-loss --router-down --light-drop

# Laptop unplugged, router and internet still up.
brownout-buddy --db /tmp/unplug.sqlite simulate unplug

# Mains still up, gateway up, internet probes failed.
brownout-buddy --db /tmp/isp.sqlite simulate offline

brownout-buddy --db /tmp/demo.sqlite history
brownout-buddy --db /tmp/demo.sqlite simulate restore
```

Scenarios apply on top of the log you point at. A fresh database starts from "on AC and online". `restore` returns to that state. `unplug` while a power outage is already open does not open a second power row; it only moves the network. Use a different `--db` or `restore` between stories.

`power-loss` with no router flag leaves the gateway unknown, so the label stays `unknown` and the prompt stub explains how to answer. `--router-up` and `--light-steady` exist for the other side of those signals. `--sentinel-silent` feeds the stub sentinel without contacting a device.

Other scenarios: `internet-down` (alias of `offline`), `lan-down`, `restore`. `--battery-percent` and `--battery-minutes` fill the battery estimate that the notification stub would have shown.

## Configuration

The annotated file is [config.example.toml](config.example.toml). It matches the built-in defaults. A short form:

```toml
poll_interval_seconds = 5
timezone = "Asia/Manila"   # empty uses the computer's zone

[network]
timeout_seconds = 2.0
failure_threshold = 2
recovery_threshold = 1
use_default_route = true

[[network.internet_probes]]
host = "1.1.1.1"           # IP literals, so DNS failure is not mistaken for "down"
port = 443

# [[network.lan_probes]]
# host = "192.168.1.1"
# port = 80

[actions]
notify = true              # stub: written to the log, not shown by the OS
command_timeout_seconds = 30
# [[actions.commands]]
# on = "power_loss"        # power_loss, power_restore, internet_down, lan_down, connectivity_restore
# argv = ["echo", "power lost"]

[classifier]
enabled = true
prompt_below = 0.6
min_score = 0.55
min_margin = 0.15

[classifier.sentinel]
enabled = false
host = ""                  # stored only; v0.1 does not connect
port = 9
```

Unknown keys are an error. Command `argv` is a list of strings and is not passed to a shell.

## Privacy

Everything Brownout Buddy stores stays on this computer: the SQLite log, the config, labels, confidence, and any ground-truth answer you type. There is no account, no telemetry, and no sync.

Connectivity checks do leave the machine in a narrow way. Internet probes open a TCP connection to the hosts in your config (by default `1.1.1.1:443` and `8.8.8.8:53`). The gateway check sends one ICMP echo to your default gateway. Those hosts see a connection or a ping from your network. The outage log is not attached. The sentinel host in config is not contacted in this version. The ambient-light path does not open a camera. Commands you configure run locally, only on live outages.

Later ideas (public status pages, update checks) will ship off until you turn them on, and this section will say what they send before that happens.

## Current status

0.1.0 is the foundation: a headless or tray monitor, a local log, a simulator, and a classifier whose live inputs are power, internet probes, and a gateway ping. Charts, native notifications, OS battery actions, the light reading, the sentinel, the one-click question, and habit learning are not done. The [roadmap](ROADMAP.md) is the plan for that work.

## TODO

Remaining work is tracked in [ROADMAP.md](ROADMAP.md) and is estimated at about **278 hours**. Paste-ready issue drafts are in [docs/issues/](docs/issues/README.md).

- [ ] Per-OS power detection — [roadmap](ROADMAP.md#phase-1-per-os-power-detection) · [draft](docs/issues/01-per-os-power-detection.md)
- [ ] Per-OS network detection — [roadmap](ROADMAP.md#phase-2-per-os-network-detection) · [draft](docs/issues/02-per-os-network-detection.md)
- [ ] Protect-work actions per OS — [roadmap](ROADMAP.md#phase-3-protect-work-actions) · [draft](docs/issues/03-protect-work-actions.md)
- [ ] Tray UI polish — [roadmap](ROADMAP.md#phase-4-tray-ui) · [draft](docs/issues/04-tray-ui.md)
- [ ] Settings UI — [roadmap](ROADMAP.md#phase-5-settings-ui) · [draft](docs/issues/05-settings-ui.md)
- [ ] Outage log charts — [roadmap](ROADMAP.md#phase-6-outage-log-and-charts) · [draft](docs/issues/06-outage-log-and-charts.md)
- [ ] Richer CSV export — [roadmap](ROADMAP.md#phase-7-csv-export) · [draft](docs/issues/07-csv-export.md)
- [ ] Native notifications — [roadmap](ROADMAP.md#phase-8-notifications) · [draft](docs/issues/08-notifications.md)
- [ ] Phone hotspot fallback — [roadmap](ROADMAP.md#phase-9-phone-hotspot-fallback) · [draft](docs/issues/09-phone-hotspot-fallback.md)
- [ ] "Is it just me or my area?" — [roadmap](ROADMAP.md#phase-10-is-it-just-me-or-my-area) · [draft](docs/issues/10-area-status-check.md)
- [ ] UPS / NUT integration — [roadmap](ROADMAP.md#phase-11-ups-and-nut-integration) · [draft](docs/issues/11-ups-nut-integration.md)
- [ ] Auto-start on login — [roadmap](ROADMAP.md#phase-12-auto-start-on-login) · [draft](docs/issues/12-autostart-on-login.md)
- [ ] Packaging, installers, and auto-update — [roadmap](ROADMAP.md#phase-13-packaging-and-auto-update) · [draft](docs/issues/13-packaging-and-auto-update.md)
- [ ] Localization (Tagalog, Cebuano) — [roadmap](ROADMAP.md#phase-14-localization) · [draft](docs/issues/14-localization.md)
- [ ] Tests and docs beyond this foundation — [roadmap](ROADMAP.md#phase-15-tests-and-docs) · [draft](docs/issues/15-tests-and-docs.md)
- [ ] Ambient light readings — [roadmap](ROADMAP.md#phase-16-ambient-light-signal) · [draft](docs/issues/16-ambient-light-signal.md)
- [ ] LAN sentinel heartbeat — [roadmap](ROADMAP.md#phase-17-lan-sentinel-heartbeat) · [draft](docs/issues/17-lan-sentinel-heartbeat.md)
- [ ] One-click "Brownout or unplugged?" prompt — [roadmap](ROADMAP.md#phase-18-brownout-or-unplugged-prompt) · [draft](docs/issues/18-confirmation-prompt.md)
- [ ] Pattern heuristics — [roadmap](ROADMAP.md#phase-19-pattern-heuristics) · [draft](docs/issues/19-pattern-heuristics.md)

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The suite covers power and network classification, the outage state machine, the debouncer, config parsing, the rule scorer, stub signals (including "a stub must not move the score"), the gateway ping command builder, light-sensor capability checks, the SQLite log, CSV, day/week stats in `Asia/Manila`, the simulator, and the CLI. It does not need a battery, a display, or a network.

GitHub Actions runs the same suite on Python 3.11 and 3.12.

## Contributing

Issues that match the roadmap are drafted in [docs/issues/](docs/issues/README.md) so they can be pasted into the tracker. Keep new behavior honest: if an OS hook is not implemented, return a stub result instead of pretending it ran. Do not add telemetry. Do not use the webcam as a light sensor.

## License

[MIT](LICENSE)
