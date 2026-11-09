"""ICMP ping for the default gateway.

Internet probes elsewhere in the app are TCP, because a handshake to a
public address needs no special permission. The classifier's gateway
signal is a real ping: the user asked to ping the router, not merely to
open a port the router may refuse.

A missing ``ping`` binary or an unexpected exit code means "unknown",
not "the router is down". One echo request with no reply means down.
"""

from __future__ import annotations

import subprocess
import sys


def ping_command(host: str, timeout: float, platform: str) -> list[str]:
    """Build a single-echo ping argv. ``host`` is one argument, never a shell line."""

    safe = _require_host(host)
    if platform == "win32":
        wait_ms = str(max(1, int(timeout * 1000)))
        return ["ping", "-n", "1", "-w", wait_ms, safe]
    if platform == "darwin":
        # macOS ping -W is milliseconds.
        wait_ms = str(max(1, int(timeout * 1000)))
        return ["ping", "-c", "1", "-W", wait_ms, safe]
    # Linux and other Unix ping -W is whole seconds.
    seconds = str(max(1, int(timeout)))
    return ["ping", "-c", "1", "-W", seconds, safe]


def icmp_ping(host: str, timeout: float) -> bool | None:
    """Return True if the host answers, False if it does not, None if ping could not be run."""

    try:
        argv = ping_command(host, timeout, sys.platform)
    except ValueError:
        return None
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            timeout=max(timeout, 1) + 2,
            check=False,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    return None


def _require_host(host: str) -> str:
    if not host or host.startswith("-") or any(character.isspace() for character in host):
        raise ValueError(f"refusing to ping {host!r}")
    return host
