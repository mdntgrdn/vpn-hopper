"""Tunnel subnet IP helpers for AWG configs."""
from __future__ import annotations

import ipaddress


def tunnel_ipv4(tunnel_subnet: str, host_number: int) -> str:
    net = ipaddress.ip_network(str(tunnel_subnet).strip(), strict=False)
    if net.version != 4:
        raise ValueError(f"tunnel_subnet must be IPv4: {tunnel_subnet}")
    hosts = list(net.hosts())
    if host_number < 1 or host_number > len(hosts):
        raise ValueError(
            f"tunnel_subnet {tunnel_subnet!r}: hop #{host_number} out of range "
            f"(usable hosts: {len(hosts)})"
        )
    return str(hosts[host_number - 1])


def tunnel_cidr(tunnel_subnet: str, host_number: int) -> str:
    net = ipaddress.ip_network(str(tunnel_subnet).strip(), strict=False)
    return f"{tunnel_ipv4(tunnel_subnet, host_number)}/{net.prefixlen}"
