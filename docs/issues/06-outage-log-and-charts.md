Title: Outage log view and charts

Labels: enhancement, storage, ui

## Description

SQLite already stores start, end, duration, type, label, confidence, and ground truth. `history` and `stats` print text. Charts are explicitly not implemented. This issue adds a local view of the log.

Estimated effort: about 16 hours.

## Acceptance criteria

- [ ] A local view charts outage minutes by day and by week without contacting the network.
- [ ] An open outage is visible with elapsed time, label, and confidence.
- [ ] The user can delete a single mistaken row, including one created by the simulator.
- [ ] A retention age can drop or archive old rows, and the default is to keep everything.
- [ ] Ground truth, when set, is visible next to the classifier label and does not replace it.
- [ ] The text `stats` command still works.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-6-outage-log-and-charts
