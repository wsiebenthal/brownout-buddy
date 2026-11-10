"""Internet and LAN detection.

Probes are TCP connections, not ICMP. A handshake needs no extra privileges
and works from a normal user session. The default targets are IP literals so
a DNS failure is not confused with "the name resolved, but we called it down".

LAN versus upstream, in this version:

* If any internet probe connects, the machine is online.
* If the user configured ``lan_probes``, those decide. One success plus failed
  internet probes means upstream is down. Every LAN probe failing means the
  LAN or router is down.
* With no LAN probes, Linux can read ``/proc/net/route``. No default route
  means LAN down. A default route plus failed internet probes means upstream
  is down.
* On other operating systems the routing table is not read yet. Failed
  internet probes are reported as ``internet_down`` with a note that LAN and
  upstream could not be separated. Configure ``lan_probes`` to distinguish
  them. Native reachability APIs are on the roadmap.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

from brownout_buddy.config import Config
from brownout_buddy.models import NetworkReading, NetworkStatus, RouteInfo


def tcp_probe(host: str, port: int, timeout: float) -> bool:
    """Return True when a TCP connection to ``host:port`` is accepted."""

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def classify_network(
    *,
    internet_up: bool,
    lan_probe_up: bool | None,
    has_default_route: bool | None,
) -> NetworkStatus:
    """Classify one round of probe results.

    ``lan_probe_up`` is None when the user did not configure LAN probes.
    ``has_default_route`` is None when this process did not check the
    routing table (unsupported OS, or the check is disabled).
    """

    if internet_up:
        return NetworkStatus.ONLINE
    if lan_probe_up is True:
        return NetworkStatus.INTERNET_DOWN
    if lan_probe_up is False:
        return NetworkStatus.LAN_DOWN
    if has_default_route is False:
        return NetworkStatus.LAN_DOWN
    return NetworkStatus.INTERNET_DOWN


def parse_proc_net_route(text: str) -> RouteInfo:
    """Parse Linux ``/proc/net/route`` and return the default gateway, if any."""

    gateway: str | None = None
    has_default = False
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        destination, gateway_hex = parts[1], parts[2]
        if destination != "00000000":
            continue
        has_default = True
        gateway = _hex_le_ipv4(gateway_hex)
        break
    return RouteInfo(
        checked=True,
        has_default_route=has_default,
        gateway=gateway,
        method="proc-net-route",
    )


def read_default_route(
    *,
    use_default_route: bool = True,
    proc_path: Path | None = None,
) -> RouteInfo:
    """Best-effort default-route lookup.

    Only Linux ``/proc/net/route`` is implemented. Other platforms return
    ``checked=False`` so the classifier will not claim the LAN is down.
    """

    if not use_default_route:
        return RouteInfo(
            checked=False,
            has_default_route=None,
            gateway=None,
            method="disabled",
        )
    if sys.platform != "linux" and proc_path is None:
        return RouteInfo(
            checked=False,
            has_default_route=None,
            gateway=None,
            method="unsupported",
        )
    path = proc_path if proc_path is not None else Path("/proc/net/route")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return RouteInfo(
            checked=False,
            has_default_route=None,
            gateway=None,
            method="unreadable",
        )
    info = parse_proc_net_route(text)
    return info


def probe_network(
    config: Config,
    *,
    probe=tcp_probe,
    route_lookup=None,
) -> NetworkReading:
    """Probe configured targets and classify the result.

    ``probe`` and ``route_lookup`` are injectable so tests do not touch the
    network. A live call uses :func:`tcp_probe` and :func:`read_default_route`.
    """

    if not config.internet_probes:
        return NetworkReading(
            status=NetworkStatus.UNKNOWN,
            note="No internet probes are configured.",
        )

    internet_results = [
        bool(probe(item.host, item.port, config.network_timeout_seconds))
        for item in config.internet_probes
    ]
    lan_results: list[bool] | None = None
    lan_probe_up: bool | None = None
    if config.lan_probes:
        lan_results = [
            bool(probe(item.host, item.port, config.network_timeout_seconds))
            for item in config.lan_probes
        ]
        lan_probe_up = any(lan_results)

    if route_lookup is None:
        route = read_default_route(use_default_route=config.use_default_route)
    else:
        route = route_lookup()

    route_flag = route.has_default_route if route.checked else None
    # Explicit LAN probes replace the route heuristic.
    if lan_probe_up is not None:
        route_flag_for_class = None
    else:
        route_flag_for_class = route_flag

    status = classify_network(
        internet_up=any(internet_results),
        lan_probe_up=lan_probe_up,
        has_default_route=route_flag_for_class,
    )
    return NetworkReading(
        status=status,
        internet_results=internet_results,
        lan_results=lan_results,
        route=route,
        note=_note(status, lan_probe_up, route),
    )


def read_network(config: Config) -> NetworkReading:
    """Live network reading using real TCP probes."""

    if not config.network_enabled:
        return NetworkReading(
            status=NetworkStatus.UNKNOWN,
            note="Network monitoring is disabled in config.",
        )
    return probe_network(config)


def _note(
    status: NetworkStatus, lan_probe_up: bool | None, route: RouteInfo
) -> str:
    if status == NetworkStatus.ONLINE:
        return ""
    if lan_probe_up is not None:
        return "Classification used configured LAN probes."
    if not route.checked:
        if route.method == "unsupported":
            return (
                "Internet probes failed. This OS cannot read the default route "
                "yet, so LAN and upstream are not separated. Add network.lan_probes "
                "to distinguish them."
            )
        if route.method == "disabled":
            return (
                "Internet probes failed. Default-route detection is off and no "
                "LAN probes are set, so this is reported as upstream internet down."
            )
        return (
            "Internet probes failed. The routing table could not be read, so "
            "this is reported as upstream internet down."
        )
    if route.has_default_route:
        gateway = f" (gateway {route.gateway})" if route.gateway else ""
        return f"Default route is present{gateway}; internet probes failed."
    return "No default route; treated as LAN or router down."


def _hex_le_ipv4(value: str) -> str | None:
    """Decode a little-endian IPv4 address from ``/proc/net/route``.

    The file format is little-endian regardless of the host CPU.
    """

    try:
        raw = bytes.fromhex(value)
    except ValueError:
        return None
    if len(raw) != 4:
        return None
    return ".".join(str(part) for part in raw[::-1])
