"""Resolve and validate a chain's body protocol from chains.yaml topology."""
from __future__ import annotations

import sys

from scripts.lib.common.topology import (
    PROTO_AWG,
    ChainTopology,
)

PROTO_AWG_BODY = "awg"


def _segment_protocols(topo: ChainTopology, host: str) -> set[str]:
    return {seg.protocol for seg in topo.segments_for(host)}


def resolve_body_protocol(topo: ChainTopology) -> str:
    """Resolve and validate the chain's body protocol as homogeneous AWG."""
    if not topo.is_awg_chain:
        print(
            f"chains.{topo.chain_name}: no AWG body found "
            "(need awg/server on every hop).",
            file=sys.stderr,
        )
        sys.exit(2)
    assert_homogeneous_awg(topo)
    return PROTO_AWG_BODY


def assert_homogeneous_awg(topo: ChainTopology) -> None:
    """Every hop must be a pure awg/server hop (no other protocols)."""
    no_server = [h for h in topo.path_hosts if not topo.has_awg_server(h)]
    if no_server:
        print(
            f"chains.{topo.chain_name}: not a homogeneous AWG chain — "
            f"hops without awg/server: {', '.join(no_server)}.",
            file=sys.stderr,
        )
        sys.exit(2)
    foreign: list[str] = []
    for host in topo.path_hosts:
        extra = _segment_protocols(topo, host) - {PROTO_AWG}
        if extra:
            foreign.append(f"{host} ({', '.join(sorted(extra))})")
    if foreign:
        print(
            f"chains.{topo.chain_name}: AWG body must contain only awg "
            f"segments — found other protocols on: {'; '.join(foreign)}.",
            file=sys.stderr,
        )
        sys.exit(2)
