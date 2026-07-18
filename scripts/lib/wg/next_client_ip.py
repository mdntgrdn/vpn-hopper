#!/usr/bin/env python3
"""Next free AllowedIPs (/32) in client_subnet for the entry node.

Reads occupied addresses from awg_clients.yml for the chain entry host.
Stdout: one line, e.g. 10.52.0.17/32.
"""
from __future__ import annotations

import argparse
import ipaddress
import sys

from scripts.lib.common.chains import load_chain_settings
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.paths import env_paths, load_yaml
from scripts.lib.wg.list_awg_clients import clients_for_host, load_awg_clients_document


def _entry_host(chain: str) -> str:
    paths = env_paths(load_chain_settings(chain_name=chain))
    gen = load_yaml(paths.chain_generated)
    host = str(gen.get("chain_entry_host") or "").strip()
    if host:
        return host
    hosts = gen.get("chain_ordered_hosts") or []
    if hosts:
        return str(hosts[0])
    print(f"Missing chain_entry_host in {paths.chain_generated}", file=sys.stderr)
    sys.exit(1)


def _ipv4_in_network(addr: str, network: ipaddress.IPv4Network) -> ipaddress.IPv4Address | None:
    s = addr.strip()
    if not s or s == "0.0.0.0/0":
        return None
    try:
        ip = ipaddress.ip_interface(s).ip
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv4Address) and ip in network:
        return ip
    return None


def collect_used_ipv4(network: ipaddress.IPv4Network, rows: list[dict]) -> set[int]:
    used: set[int] = set()
    for r in rows:
        ips = r.get("allowed_ips")
        if not ips:
            continue
        for part in str(ips).split(","):
            ip = _ipv4_in_network(part, network)
            if ip is not None:
                used.add(int(ip))
    return used


def next_allowed_ip(network: ipaddress.IPv4Network, used: set[int]) -> str:
    for ip in network.hosts():
        if int(ip) not in used:
            return f"{ip}/32"
    print("No free addresses left in client_subnet.", file=sys.stderr)
    sys.exit(2)


def compute_next_ip(chain: str) -> str:
    settings = load_chain_settings(chain_name=chain)
    paths = env_paths(settings)
    entry = _entry_host(chain)
    net = ipaddress.ip_network(str(settings["client_subnet"]).strip(), strict=False)
    if not isinstance(net, ipaddress.IPv4Network):
        print("client_subnet must be IPv4.", file=sys.stderr)
        sys.exit(1)
    rows = clients_for_host(load_awg_clients_document(paths.awg_clients), entry)
    return next_allowed_ip(net, collect_used_ipv4(net, rows))


def main() -> None:
    ap = argparse.ArgumentParser(description="Next free /32 in client_subnet for entry")
    add_chain_cli(ap)
    args = ap.parse_args()
    sys.stdout.write(compute_next_ip(args.chain))


if __name__ == "__main__":
    main()
