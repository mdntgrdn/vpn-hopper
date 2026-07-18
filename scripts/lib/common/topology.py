#!/usr/bin/env python3
"""Parse chains.yaml chains.path into an AWG chain topology.

Every hop runs a single ``awg`` server segment; positions (entry|middle|exit)
are inferred from path order.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

PROTO_AWG = "awg"
PROTO_VLESS_HTTP = "vless-http"
PROTO_VLESS_GRPC = "vless-grpc"
WRAPPER_PROTOCOLS = (PROTO_VLESS_HTTP, PROTO_VLESS_GRPC)
ROLE_SERVER = "server"
POS_ENTRY = "entry"
POS_MIDDLE = "middle"
POS_EXIT = "exit"
CHAIN_SERVER_POSITIONS = (POS_ENTRY, POS_MIDDLE, POS_EXIT)


@dataclass(frozen=True)
class Segment:
    protocol: str
    role: str
    raw: dict[str, Any]

    @property
    def position(self) -> str | None:
        p = self.raw.get("position")
        return str(p).strip() if p else None


@dataclass
class PathHop:
    host: str
    segments: list[Segment]
    wrapper: dict[str, Any] | None = None


@dataclass
class ChainTopology:
    chain_name: str
    path: list[PathHop]
    host_meta: dict[str, dict[str, Any]]
    deploy_settings: dict[str, Any]
    client_subnet: str

    @property
    def path_hosts(self) -> list[str]:
        return [h.host for h in self.path]

    @property
    def is_awg_chain(self) -> bool:
        return bool(self.awg_server_hosts)

    @property
    def awg_server_hosts(self) -> list[str]:
        """All awg/server hops in path order."""
        out: list[str] = []
        for hop in self.path:
            for seg in hop.segments:
                if seg.protocol == PROTO_AWG and seg.role == ROLE_SERVER:
                    if hop.host not in out:
                        out.append(hop.host)
        return out

    @property
    def awg_chain_server_hosts(self) -> list[str]:
        """Tunnel chain (entry → middle → exit). Same as awg_server_hosts."""
        return self.awg_server_hosts

    def awg_deploy_hosts(self) -> list[str]:
        """Hosts that need the AWG Docker image."""
        return list(self.awg_server_hosts)

    @property
    def entry_host(self) -> str:
        servers = self.awg_server_hosts
        if servers:
            return servers[0]
        _die(f"chains.{self.chain_name}: no entry host (need an awg/server hop).")
        return ""

    @property
    def exit_host(self) -> str:
        servers = self.awg_server_hosts
        if servers:
            return servers[-1]
        _die(f"chains.{self.chain_name}: no exit host (need an awg/server hop).")
        return ""

    def has_awg_server(self, host: str) -> bool:
        return host in self.awg_server_hosts

    def has_awg_chain_server(self, host: str) -> bool:
        return host in self.awg_chain_server_hosts

    def awg_server_index(self, host: str) -> int:
        return self.awg_chain_server_hosts.index(host)

    def awg_listen_port(self, host: str, base_port: int) -> int:
        """UDP ListenPort / client Endpoint port: awg.base_port + hop index."""
        base = int(base_port)
        if host in self.awg_chain_server_hosts:
            return base + self.awg_server_index(host)
        return base

    def segments_for(self, host: str) -> list[Segment]:
        for hop in self.path:
            if hop.host == host:
                return hop.segments
        return []

    @property
    def wrapper_hops(self) -> list[tuple[str, dict[str, Any]]]:
        """(host, wrapper-config) for every hop that carries a wrapper:."""
        return [(hop.host, hop.wrapper) for hop in self.path if hop.wrapper]

    @property
    def has_wrapper(self) -> bool:
        return bool(self.wrapper_hops)

    @property
    def wrapper_host(self) -> str:
        """Host that runs the protocol wrapper (co-located with the AWG entry)."""
        hops = self.wrapper_hops
        return hops[0][0] if hops else ""

    def wrapper_config(self, host: str = "") -> dict[str, Any] | None:
        """Normalized wrapper config for the wrapper host (or the only wrapper)."""
        for whost, cfg in self.wrapper_hops:
            if not host or whost == host:
                return cfg
        return None


def _die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_hosts_catalog(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = doc.get("hosts")
    if raw is None:
        raw = doc.get("servers")
    if raw is None:
        _die("chains.yaml requires top-level hosts: (or legacy servers:) catalog.")
    if not isinstance(raw, dict) or not raw:
        _die("chains.yaml hosts: must be a non-empty dict.")
    return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}


def _awg_server_segment(hop: PathHop) -> Segment | None:
    for seg in hop.segments:
        if seg.protocol == PROTO_AWG and seg.role == ROLE_SERVER:
            return seg
    return None


def infer_awg_positions(path: list[PathHop]) -> None:
    """Derive position (entry|middle|exit) from path order of awg/server hops."""
    servers = [hop for hop in path if _awg_server_segment(hop)]
    n = len(servers)
    for i, hop in enumerate(servers):
        awg = _awg_server_segment(hop)
        if awg is None or (awg.raw.get("position") or "").strip():
            continue
        if i == 0:
            awg.raw["position"] = POS_ENTRY
        elif i == n - 1:
            awg.raw["position"] = POS_EXIT
        else:
            awg.raw["position"] = POS_MIDDLE


def _parse_segment(raw: Any, *, chain_name: str, host: str) -> Segment:
    if not isinstance(raw, dict):
        _die(f"chains.{chain_name} path {host!r}: segment must be a dict.")
    proto = str(raw.get("protocol") or "").strip().lower()
    if proto != PROTO_AWG:
        _die(
            f"chains.{chain_name} path {host!r}: only protocol: awg is supported "
            f"(got {proto!r})."
        )
    role = str(raw.get("role") or "").strip().lower()
    if role and role != ROLE_SERVER:
        _die(f"chains.{chain_name} path {host!r}: awg role must be server.")
    return Segment(protocol=PROTO_AWG, role=ROLE_SERVER, raw=raw)


def _parse_wrapper(raw: Any, *, chain_name: str, host: str) -> dict[str, Any]:
    """Normalize a hop ``wrapper:`` block (entry-node protocol wrapper)."""
    if not isinstance(raw, dict):
        _die(f"chains.{chain_name} path {host!r}: wrapper must be a dict.")
    proto = str(raw.get("protocol") or "").strip().lower()
    if proto not in WRAPPER_PROTOCOLS:
        _die(
            f"chains.{chain_name} path {host!r}: wrapper.protocol must be one of "
            f"{', '.join(WRAPPER_PROTOCOLS)} (got {proto!r})."
        )
    server_name = str(raw.get("server_name") or raw.get("sni") or "").strip()
    if not server_name:
        _die(f"chains.{chain_name} path {host!r}: wrapper requires server_name.")
    out = dict(raw)
    out["protocol"] = proto
    out["server_name"] = server_name
    out["listen_port"] = int(raw.get("listen_port") or 443)
    # gRPC transport only: service path; defaulted by the renderer when empty.
    out["service_name"] = str(raw.get("service_name") or "").strip()
    return out


def _validate_wrappers(topo: ChainTopology) -> None:
    name = topo.chain_name
    wrappers = topo.wrapper_hops
    if not wrappers:
        return
    if len(wrappers) > 1:
        hosts = ", ".join(h for h, _ in wrappers)
        _die(f"chains.{name}: only one wrapper is supported (found on: {hosts}).")
    whost, _ = wrappers[0]
    if whost != topo.entry_host:
        _die(
            f"chains.{name}: wrapper is only allowed on the entry host "
            f"{topo.entry_host!r} (found on {whost!r})."
        )


def _validate_topology(topo: ChainTopology) -> None:
    name = topo.chain_name
    if not topo.is_awg_chain:
        _die(f"chains.{name}: path needs at least one awg/server hop.")

    positions: list[tuple[str, str]] = []
    for hop in topo.path:
        for seg in hop.segments:
            if seg.protocol == PROTO_AWG and seg.role == ROLE_SERVER:
                pos = seg.position
                if not pos or pos not in CHAIN_SERVER_POSITIONS:
                    _die(
                        f"chains.{name} path {hop.host!r}: awg segment has invalid "
                        f"position {pos!r} (expected entry|middle|exit)."
                    )
                positions.append((hop.host, pos))

    chain_servers = topo.awg_chain_server_hosts
    entries = [h for h, p in positions if p == POS_ENTRY]

    if len(chain_servers) == 1:
        if len(entries) != 1:
            _die(f"chains.{name}: single-hop chain must be position: entry.")
        _validate_wrappers(topo)
        return

    exits = [h for h, p in positions if p == POS_EXIT]
    if len(entries) != 1:
        _die(f"chains.{name}: exactly one awg/server position: entry (found {len(entries)}).")
    if len(exits) != 1:
        _die(f"chains.{name}: exactly one awg/server position: exit (found {len(exits)}).")
    if chain_servers[0] != entries[0]:
        _die(f"chains.{name}: first awg/server in path must be position: entry.")
    if chain_servers[-1] != exits[0]:
        _die(f"chains.{name}: last awg/server in path must be position: exit.")
    _validate_wrappers(topo)


def extract_deploy_settings(entry: dict[str, Any], chain_name: str) -> dict[str, Any]:
    """awg: block and chain-level keys; deploy name on server = chain name (chains.<name>)."""
    mapping = {
        "base_port": "awg_base_port",
        "awg_base_port": "awg_base_port",
        "tunnel_subnet": "tunnel_subnet",
        "routing_table": "routing_table",
        "wan_iface": "wan_iface",
        "deploy_dir": "deploy_dir",
        "docker_image_name": "docker_image_name",
        "docker_container_name": "docker_container_name",
        "client_subnet": "client_subnet",
    }
    out: dict[str, Any] = {}
    awg = entry.get("awg")
    if isinstance(awg, dict):
        for src, dst in mapping.items():
            if src in awg and awg[src] is not None:
                out[dst] = awg[src]
    for src, dst in mapping.items():
        if src in entry and entry[src] is not None and dst not in out:
            out[dst] = entry[src]
    return out


def resolve_client_subnet(
    path: list[PathHop],
    deploy_settings: dict[str, Any],
    *,
    chain_name: str,
) -> str:
    """Single client pool per chain: chains.<name>.awg.client_subnet."""
    _ = path
    cs = str(deploy_settings.get("client_subnet") or "").strip()
    if not cs:
        _die(
            f"chains.{chain_name}: set awg.client_subnet (client VPN pool for the whole chain)."
        )
    return cs


def path_from_legacy_servers(
    servers: list | dict,
    *,
    catalog: dict[str, dict],
    chain_name: str,
) -> list[dict]:
    """Convert chains.<name>.servers list/dict → path items (one awg hop per host)."""
    names: list[str] = []
    if isinstance(servers, list):
        for item in servers:
            if isinstance(item, str):
                names.append(item.strip())
            elif isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
            else:
                _die(f"chains.{chain_name}.servers: invalid list item.")
    elif isinstance(servers, dict):
        names = list(servers.keys())
    else:
        _die(f"chains.{chain_name}.servers must be list or dict.")

    if not names:
        _die(f"chains.{chain_name}.servers is empty.")

    path_raw: list[dict] = []
    for name in names:
        if name not in catalog:
            _die(f"chains.{chain_name}.servers: {name!r} not in hosts catalog.")
        path_raw.append({"host": name, "protocol": PROTO_AWG})
    return path_raw


def awg_position_for_host(topo: ChainTopology, host: str) -> str:
    """Resolved AWG position on host (entry|middle|exit), after infer_awg_positions."""
    for seg in topo.segments_for(host):
        if seg.protocol == PROTO_AWG and seg.role == ROLE_SERVER:
            return str(seg.position or "").strip()
    return ""


def build_chain_topology(
    *,
    chain_name: str,
    entry: dict[str, Any],
    doc: dict[str, Any],
) -> ChainTopology:
    """Parse chains.yaml path, infer AWG positions, validate — call once at inventory start."""
    _names, _rows, _meta, topo = parse_chain_path(chain_name=chain_name, entry=entry, doc=doc)
    return topo


_HOP_RESERVED_KEYS = ("host", "segments", "wrapper")


def _hop_segments_and_meta(
    item: dict[str, Any],
    *,
    chain_name: str,
    host: str,
) -> tuple[list[dict], dict[str, Any], dict[str, Any] | None]:
    """Resolve a path hop into (segments_raw, host_meta_override, wrapper).

    Two surface forms are accepted:
      - inline shortcut: {host, protocol: awg, <segment fields>}  -> single segment
      - explicit list:   {host, segments: [ {protocol: awg}, ... ], <meta overrides>}

    An optional ``wrapper:`` block (entry-node protocol wrapper) is parsed out of
    the hop and never becomes part of the awg segment. In the inline form every
    key except ``host`` and ``wrapper`` belongs to the single segment; per-hop
    host-meta overrides are only available via the explicit ``segments`` form.
    """
    wrapper_raw = item.get("wrapper")
    wrapper = (
        _parse_wrapper(wrapper_raw, chain_name=chain_name, host=host)
        if wrapper_raw is not None
        else None
    )

    segs_raw = item.get("segments")
    if segs_raw is not None:
        if not isinstance(segs_raw, list) or not segs_raw:
            _die(f"chains.{chain_name} path {host!r}: segments must be a non-empty list.")
        if "protocol" in item:
            _die(
                f"chains.{chain_name} path {host!r}: set either protocol: (single segment) "
                "or segments: (list), not both."
            )
        meta_override = {k: v for k, v in item.items() if k not in _HOP_RESERVED_KEYS}
        return segs_raw, meta_override, wrapper

    if item.get("protocol"):
        segment = {k: v for k, v in item.items() if k not in _HOP_RESERVED_KEYS}
        return [segment], {}, wrapper

    _die(
        f"chains.{chain_name} path {host!r}: set protocol: awg (or a segments: list)."
    )
    return [], {}, None  # unreachable; _die raises


def parse_chain_path(
    *,
    chain_name: str,
    entry: dict[str, Any],
    doc: dict[str, Any],
) -> tuple[list[str], list[dict], dict[str, dict], ChainTopology]:
    catalog = load_hosts_catalog(doc)
    deploy_settings = extract_deploy_settings(entry, chain_name)

    path_raw = entry.get("path")
    if path_raw is None:
        servers = entry.get("servers")
        if servers is None:
            _die(f"chains.{chain_name} requires path: (or legacy servers:).")
        path_raw = path_from_legacy_servers(servers, catalog=catalog, chain_name=chain_name)
        print(
            f"Note: chains.{chain_name} uses legacy servers: — consider migrating to path:",
            file=sys.stderr,
        )

    if not isinstance(path_raw, list) or not path_raw:
        _die(f"chains.{chain_name} path must be a non-empty list.")

    path: list[PathHop] = []
    meta: dict[str, dict] = {}

    for item in path_raw:
        if not isinstance(item, dict):
            _die(f"chains.{chain_name} path items must be dicts with host: and protocol:.")
        host_key = str(item.get("host") or "").strip()
        if not host_key:
            _die(f"chains.{chain_name} path item missing host:.")
        if host_key not in catalog:
            known = ", ".join(sorted(catalog)) or "(empty)"
            _die(f"chains.{chain_name} path host {host_key!r} not in hosts catalog ({known}).")

        segs_raw, meta_override, wrapper = _hop_segments_and_meta(
            item, chain_name=chain_name, host=host_key
        )
        base = dict(catalog[host_key])
        base.update(meta_override)
        meta[host_key] = base
        segments = [_parse_segment(s, chain_name=chain_name, host=host_key) for s in segs_raw]
        path.append(PathHop(host=host_key, segments=segments, wrapper=wrapper))

    infer_awg_positions(path)

    client_subnet = resolve_client_subnet(path, deploy_settings, chain_name=chain_name)

    topo = ChainTopology(
        chain_name=chain_name,
        path=path,
        host_meta=meta,
        deploy_settings=deploy_settings,
        client_subnet=client_subnet,
    )
    _validate_topology(topo)

    rows: list[dict] = []
    for hop in path:
        row = dict(meta[hop.host])
        row["_inventory_name"] = hop.host
        rows.append(row)

    return topo.path_hosts, rows, meta, topo


def subnet_last_host(cidr: str) -> str:
    """Last usable host in client_subnet (SNAT source identity at the entry)."""
    import ipaddress

    net = ipaddress.ip_network(str(cidr).strip(), strict=False)
    hosts = list(net.hosts())
    if not hosts:
        _die(f"client_subnet {cidr!r} has no usable host addresses")
    return str(hosts[-1])


def gateway_snat_source(topo: ChainTopology, host: str) -> str:
    """SNAT --to-source for the entry node (override via segment snat_source: or pool last host)."""
    for s in topo.segments_for(host):
        if s.protocol == PROTO_AWG and s.role == ROLE_SERVER and s.raw.get("snat_source"):
            return str(s.raw["snat_source"]).strip()
    if not topo.client_subnet:
        _die(f"chains.{topo.chain_name}: client_subnet required for entry SNAT source.")
    return subnet_last_host(topo.client_subnet)
