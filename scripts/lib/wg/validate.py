"""Cross-chain AWG isolation: ports, tunnel_subnet, client_subnet, routing_table."""
from __future__ import annotations

import ipaddress
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from scripts.lib.common.topology import extract_deploy_settings


@dataclass(frozen=True)
class ChainNet:
    name: str
    base_port: int | None
    port_count: int
    tunnel_subnet: ipaddress.IPv4Network | None
    client_subnet: ipaddress.IPv4Network | None
    routing_table: int | None


def _parse_net(value: Any) -> ipaddress.IPv4Network | None:
    s = str(value or "").strip()
    if not s:
        return None
    return ipaddress.ip_network(s, strict=False)


def _usable_port_count(tunnel: ipaddress.IPv4Network | None) -> int:
    """Reserved ports per chain = base_port + (usable hosts in tunnel_subnet)."""
    if tunnel is None:
        return 1
    return max(len(list(tunnel.hosts())), 1)


def _collect(doc: dict[str, Any]) -> list[ChainNet]:
    chains = doc.get("chains")
    if not isinstance(chains, dict):
        return []
    out: list[ChainNet] = []
    for name in sorted(chains):
        entry = chains.get(name)
        if not isinstance(entry, dict):
            continue
        settings = extract_deploy_settings(entry, name)
        try:
            tunnel = _parse_net(settings.get("tunnel_subnet"))
            client = _parse_net(settings.get("client_subnet"))
        except ValueError as exc:
            print(f"chains.{name}: invalid subnet — {exc}", file=sys.stderr)
            sys.exit(1)
        bp_raw = settings.get("awg_base_port")
        base_port = int(bp_raw) if bp_raw is not None and str(bp_raw).strip() != "" else None
        rt_raw = settings.get("routing_table")
        routing_table = (
            int(rt_raw) if rt_raw is not None and str(rt_raw).strip() != "" else None
        )
        out.append(
            ChainNet(
                name=name,
                base_port=base_port,
                port_count=_usable_port_count(tunnel),
                tunnel_subnet=tunnel,
                client_subnet=client,
                routing_table=routing_table,
            )
        )
    return out


def _check_port_overlaps(nets: list[ChainNet]) -> list[str]:
    errors: list[str] = []
    ranged = [n for n in nets if n.base_port is not None]
    for i in range(len(ranged)):
        for j in range(i + 1, len(ranged)):
            a, b = ranged[i], ranged[j]
            a_start, a_end = a.base_port, a.base_port + a.port_count
            b_start, b_end = b.base_port, b.base_port + b.port_count
            if a_start < b_end and b_start < a_end:
                errors.append(
                    f"port range overlap: {a.name} [{a_start}..{a_end - 1}] "
                    f"({a.port_count} ports) and {b.name} [{b_start}..{b_end - 1}] "
                    f"({b.port_count} ports) — each chain reserves base_port + "
                    "(usable hosts in tunnel_subnet)."
                )
    return errors


def _check_subnet_overlaps(
    nets: list[ChainNet],
    attr: str,
    label: str,
) -> list[str]:
    errors: list[str] = []
    have = [n for n in nets if getattr(n, attr) is not None]
    for i in range(len(have)):
        for j in range(i + 1, len(have)):
            a, b = have[i], have[j]
            net_a, net_b = getattr(a, attr), getattr(b, attr)
            if net_a.overlaps(net_b):
                errors.append(
                    f"{label} overlap: {a.name} ({net_a}) and {b.name} ({net_b})."
                )
    return errors


def _check_routing_table_collisions(nets: list[ChainNet]) -> list[str]:
    by_table: dict[int, list[str]] = defaultdict(list)
    for n in nets:
        if n.routing_table is not None:
            by_table[n.routing_table].append(n.name)
    errors: list[str] = []
    for table, names in sorted(by_table.items()):
        if len(names) > 1:
            errors.append(
                f"routing_table {table} reused by: {', '.join(sorted(names))} "
                "(each chain needs a unique routing_table)."
            )
    return errors


def validate_chain_isolation(doc: dict[str, Any]) -> list[str]:
    """Return a list of conflict messages across all chains (empty when isolated)."""
    nets = _collect(doc)
    errors: list[str] = []
    errors += _check_port_overlaps(nets)
    errors += _check_subnet_overlaps(nets, "tunnel_subnet", "tunnel_subnet")
    errors += _check_subnet_overlaps(nets, "client_subnet", "client_subnet")
    errors += _check_routing_table_collisions(nets)
    return errors


def assert_chain_isolation(doc: dict[str, Any]) -> None:
    """Exit non-zero if any cross-chain port / subnet / routing_table conflict is found."""
    errors = validate_chain_isolation(doc)
    if errors:
        print("chains.yaml: cross-chain conflicts detected:", file=sys.stderr)
        for msg in errors:
            print(f"  - {msg}", file=sys.stderr)
        sys.exit(2)
