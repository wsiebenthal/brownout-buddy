Title: Localization, including Tagalog and Cebuano

Labels: enhancement, localization, documentation

## Description

The interface is English. People dealing with frequent brownouts include Tagalog and Cebuano speakers. This issue extracts strings and adds those two catalogs. English stays the source language. Classifier labels stored in SQLite stay the English tokens (`brownout`, `unplugged`, `isp-outage`, `unknown`) so the log does not depend on the UI language. Display strings can be translated.

Estimated effort: about 12 hours.

## Acceptance criteria

- [ ] User-visible sentences go through a message catalog. Log tokens and CLI scenario names stay stable.
- [ ] Tagalog and Cebuano catalogs cover every key, including the "Brownout or unplugged?" question.
- [ ] A test fails if a key is missing from a catalog.
- [ ] Locale can be selected in config and does not require a reinstall.
- [ ] A missing translation falls back to English rather than a key name in the menu.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-14-localization
