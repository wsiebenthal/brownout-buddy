Title: OS-level tests and troubleshooting docs

Labels: documentation, tests

## Description

Unit tests cover the pure classifiers, the scorer, the log, and the CLI without hardware. They do not boot a real desktop session. This issue adds the platform checks and a troubleshooting page for the false alarms people will actually hit.

Estimated effort: about 16 hours.

## Acceptance criteria

- [ ] A documented manual or VM script covers one sleep/wake and one unplug on macOS, Windows, and Linux.
- [ ] A troubleshooting page explains captive portals, a router on a UPS, "no battery" on a desktop, and a ping binary that cannot be run.
- [ ] The page links to the classifier caveat already in the README.
- [ ] `docs/issues/` is updated when a phase's scope changes, or the contributing note says who does that.
- [ ] CI stays green without a display and without a battery.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-15-tests-and-docs
