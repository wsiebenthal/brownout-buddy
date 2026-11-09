Title: Native notifications

Labels: enhancement, notifications, macos, windows, linux

## Description

On a live outage the monitor builds a sentence (battery time remaining when known, plus the classifier label) and records it as `action notify: stub`. Nothing is shown by the OS. This issue delivers that sentence as a real notification.

Estimated effort: about 10 hours.

## Acceptance criteria

- [ ] macOS, Windows, and Linux each show the same sentence through a native notification API.
- [ ] If the OS notification API is missing, the result stays `stub` or `error` and names the reason. It must not claim success.
- [ ] Quiet hours and a minimum gap suppress repeats while a flapping probe is debounced.
- [ ] Paused monitoring sends nothing.
- [ ] The simulator still does not notify.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-8-notifications
