Title: Richer CSV export

Labels: enhancement, storage

## Description

`brownout-buddy export` writes every row, including label, confidence, and ground truth. It has no filters. This issue adds the filters and a stable column set.

Estimated effort: about 6 hours.

## Acceptance criteria

- [ ] Export can limit rows by type, label, and a start/end date.
- [ ] Timestamps can be written in the configured time zone or in UTC, and the file says which.
- [ ] Column names stay stable if more columns are added later (new columns append).
- [ ] An empty filter result still writes the header.
- [ ] Existing CSV tests cover the filtered path.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-7-csv-export
