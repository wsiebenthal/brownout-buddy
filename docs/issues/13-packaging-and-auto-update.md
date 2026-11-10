Title: Packaging, installers, and auto-update

Labels: enhancement, packaging, macos, windows, linux

## Description

Installation today is `pip install -e .` from a checkout. People who only want the tray app need an installer. An update check, if it exists, has to be off until the user enables it, and the privacy section has to describe it in the same change.

Estimated effort: about 22 hours.

## Acceptance criteria

- [ ] A documented one-folder or one-file build exists for macOS, Windows, and Linux and includes the tray extra.
- [ ] The build runs `brownout-buddy simulate` against its own code on a machine without a Python toolchain.
- [ ] Installers are signed where the OS blocks unsigned apps, or the docs say the build is unsigned and what that means.
- [ ] Update checks do nothing unless a config flag is true.
- [ ] Turning the flag on is mentioned in the README privacy section, including the host that is contacted.
- [ ] The app still stores the outage log only on the local disk.

## Roadmap

https://github.com/wsiebenthal/brownout-buddy/blob/main/ROADMAP.md#phase-13-packaging-and-auto-update
