Title: UPS and NUT integration

Labels: enhancement, detection, ups

## Description

Two different UPS cases matter. The laptop may still be on a UPS after the wall fails, so psutil still says AC. The router may be on a UPS, so the gateway ping stays up during a real brownout and the classifier leans "unplugged". NUT (`upsc`) can see the first case. The second case stays a documented limit of the gateway signal unless the UPS is the one NUT is watching.

Estimated effort: about 14 hours.

## Acceptance criteria

- [ ] Config names a NUT host and a UPS. The default is off, and an empty config does not spawn `upsc`.
- [ ] `OL` versus `OB` (on line versus on battery) is mapped into the power reading, with the method string `nut`.
- [ ] A wall failure reported by NUT can open a power outage while the laptop PSU still says AC, and the detail says it came from NUT.
- [ ] If `upsc` is missing or times out, the result is `unknown` with a note, not a fake brownout.
- [ ] Docs keep the sentence: a router on a UPS removes the gateway signal.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-11-ups-and-nut-integration
