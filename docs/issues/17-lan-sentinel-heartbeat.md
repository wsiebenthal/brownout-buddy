Title: LAN sentinel heartbeat

Labels: enhancement, classifier, network

## Description

An always-powered device on the LAN (a smart plug, or a phone left on a charger) going silent is evidence the building lost power, not just the laptop cable. Config already has `classifier.sentinel.host`. Version 0.1 stores that host and does not contact it. `--sentinel-silent` only injects a reading so the scorer can be tested. A phone that sleeps must not look like a brownout by itself.

Estimated effort: about 14 hours.

## Acceptance criteria

- [ ] A documented heartbeat (a tiny companion, or a poll of an explicit host and port) distinguishes alive from silent.
- [ ] The default config still has the sentinel disabled and makes no connection.
- [ ] A configured host that has never answered is `unknown`, not `silent`.
- [ ] Silence while AC is lost adds the brownout vote. A live heartbeat adds the unplugged vote.
- [ ] A single missed heartbeat inside the timeout does not flip a high-confidence gateway result.
- [ ] The README privacy section says the sentinel host is contacted only after the user enables it.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-17-lan-sentinel-heartbeat
