Title: Phone hotspot fallback

Labels: enhancement, network

## Description

When the upstream link dies, a phone hotspot is a common workaround. Version 0.1 has no Wi-Fi awareness. Joining a hotspot should not be logged as a second outage, and a hotspot SSID must be one the user marked, not every phone name the scan sees.

Estimated effort: about 14 hours.

## Acceptance criteria

- [ ] The user can mark one or two SSIDs as "my hotspot".
- [ ] On upstream loss, the menu offers to join a marked hotspot, with a per-OS action that is either real or an honest stub.
- [ ] The transition from the failed network to the hotspot is not a new outage if it finishes within a short grace period.
- [ ] Unmarked SSIDs are never joined automatically.
- [ ] No hotspot credential is written to the outage log.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-9-phone-hotspot-fallback
