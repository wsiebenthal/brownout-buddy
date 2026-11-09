Title: Read the ambient light sensor

Labels: enhancement, classifier, macos, windows, linux

## Description

The light signal is a stub. `detect_light` reports whether a sensor seems to exist: Linux IIO illuminance files, a not-yet-called `Windows.Devices.Sensors.LightSensor`, and an explicit unsupported result on macOS. Live lux is not read, so the scorer ignores the signal unless `--light-drop` or `--light-steady` injects a value. The webcam must not be used on any platform.

Estimated effort: about 16 hours.

## Acceptance criteria

- [ ] Windows reads `Windows.Devices.Sensors.LightSensor` when the capability check says a sensor is present, and skips the signal when it is not.
- [ ] Linux reads IIO illuminance and emits `dropped` or `steady` by comparing the level at AC loss with the level just before it.
- [ ] macOS stays on the documented stub unless a documented API is found, and the README says which choice was made.
- [ ] No code path opens a camera, `/dev/video*`, or a screenshot API to estimate brightness.
- [ ] A machine with no sensor still classifies from the other signals, and the stored reading says the light signal was skipped.
- [ ] An injected `--light-drop` still works for tests that have no sensor.
- [ ] A real drop adds the brownout vote, a steady reading adds the unplugged vote, and a stub reading adds neither.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-16-ambient-light-signal
