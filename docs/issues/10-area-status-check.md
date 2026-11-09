Title: Is it just me or my area

Labels: enhancement, network, privacy

## Description

A local measurement cannot tell a neighborhood outage from a single house. Public status pages (a utility or an ISP) can be a hint. This must be opt-in. The README privacy section has to name the host before the feature is enabled by default. It is not enabled by default.

Estimated effort: about 12 hours.

## Acceptance criteria

- [ ] A config list of status-page URLs is empty by default, and an empty list makes no request.
- [ ] A fetch uses a short timeout, a size limit, and no cookies from the user's browser.
- [ ] The menu shows the page's summary next to the local classifier label and attributes it to that page.
- [ ] A failed fetch leaves the local label unchanged and says the area check was unavailable.
- [ ] The privacy section of the README lists the request before the feature can be turned on in the sample config.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-10-is-it-just-me-or-my-area
