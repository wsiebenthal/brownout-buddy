"""Power and network classifiers.

Platform readers live beside the pure functions so tests can exercise the
decisions without a battery, a route, or a network.
"""

from brownout_buddy.detection.network import (
    classify_network,
    parse_proc_net_route,
    probe_network,
    read_network,
    tcp_probe,
)
from brownout_buddy.detection.power import interpret_battery, read_power

__all__ = [
    "classify_network",
    "interpret_battery",
    "parse_proc_net_route",
    "probe_network",
    "read_network",
    "read_power",
    "tcp_probe",
]
