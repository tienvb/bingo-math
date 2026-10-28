"""IP suggestions for `GET /api/network` (hints only, see *Hợp đồng REST API*)."""

from __future__ import annotations

import contextlib
import ipaddress
import socket
from pathlib import Path

DOCKERENV = Path("/.dockerenv")


def in_docker() -> bool:
    return DOCKERENV.exists()


def is_private_lan_ipv4(ip: str) -> bool:
    """10.x, 172.16-31.x, 192.168.x (no loopback, link-local, etc.)."""
    try:
        addr = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    return any(
        addr in ipaddress.IPv4Network(net) for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    )


def _candidate_ips() -> list[str]:
    found: list[str] = []
    # Address of the interface holding the default route (no packet is sent for UDP connect).
    with contextlib.suppress(OSError), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(0.2)
        s.connect(("10.255.255.255", 1))
        found.append(s.getsockname()[0])
    with contextlib.suppress(OSError):
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(str(info[4][0]))
    return found


def suggested_ips(lan_ip: str | None) -> list[str]:
    if in_docker():
        return [lan_ip] if lan_ip else []
    ips: list[str] = []
    for ip in ([lan_ip] if lan_ip else []) + _candidate_ips():
        if ip not in ips and (ip == lan_ip or is_private_lan_ipv4(ip)):
            ips.append(ip)
    return ips
