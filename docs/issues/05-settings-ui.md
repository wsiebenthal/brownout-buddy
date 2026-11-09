Title: Settings window

Labels: enhancement, ui

## Description

The settings menu item tells the user to edit TOML. `init-config` writes the annotated example. This issue adds a local window for the same keys the TOML loader already validates. It must not embed a remote page.

Estimated effort: about 16 hours.

## Acceptance criteria

- [ ] The window edits probes, poll interval, thresholds, action commands, classifier thresholds, and the sentinel host.
- [ ] Invalid values fail with the same messages as `load_config`.
- [ ] Save writes the user config path. Revert reloads it.
- [ ] Comments in an existing file are not silently destroyed, or the UI refuses to round-trip and says so before saving.
- [ ] No network request is made to open or save settings.
- [ ] The tray item opens this window instead of the stub sentence.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-5-settings-ui
