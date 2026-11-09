Title: Per-OS network detection

Labels: enhancement, detection, macos, windows, linux

## Description

Version 0.1 classifies connectivity with TCP probes plus, on Linux, `/proc/net/route`. The classifier separately pings the default gateway. macOS and Windows cannot read the route yet, so a failed internet probe is reported as upstream-down unless the user adds `lan_probes`. Captive portals and DNS failures can still look like an ISP outage.

Estimated effort: about 20 hours. The gateway-on-a-UPS caveat stays: a gateway that answers is not proof the laptop was merely unplugged.

## Acceptance criteria

- [ ] macOS and Windows discover the default gateway the same way Linux already does, and the ping signal uses that address.
- [ ] A captive portal is not stored as `isp-outage`.
- [ ] A DNS failure with a working IP probe is not stored as an outage.
- [ ] Internet probes prefer IP literals. Hostname probes are optional and documented as DNS-dependent.
- [ ] Probing stops early once one internet target accepts a connection.
- [ ] Docs and a test state that a router on a UPS keeps signal 2 quiet during a real brownout.
- [ ] When the route cannot be read and no LAN probe is set, the note still says LAN and upstream were not separated.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-2-per-os-network-detection
