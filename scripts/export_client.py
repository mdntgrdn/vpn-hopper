#!/usr/bin/env python3
"""
Re-export client config(s) for clients already registered on the chain.

  python3 scripts/export_client.py --chain awg-3hop -u "Alice,Bob"
  python3 scripts/export_client.py --chain awg-3hop -u "Alice" -u "Bob,Carol"

Names are listed inside -u, comma-separated; -u may be repeated.
Writes the AWG .conf, and (when the chain has a wrapper) the vless .txt/.json,
for existing clients — nothing is added or changed on the nodes.
"""
from __future__ import annotations

import argparse

from scripts.lib.common.chains import load_chain_topology
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.protocol import PROTO_AWG_BODY, resolve_body_protocol
from scripts.lib.wg.export_clients import export_clients as export_wg_clients
from scripts.lib.wg.peer_batch import parse_u_names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="export_client",
        description="Re-export config(s) for existing clients on the chain.",
        usage='%(prog)s --chain NAME -u "A,B,C" [-u "…"]',
    )
    add_chain_cli(ap)
    ap.add_argument(
        "-u",
        dest="u_names",
        action="append",
        required=True,
        metavar="NAMES",
        help="Client name(s), comma-separated; -u may be repeated.",
    )
    args = ap.parse_args(argv)

    names = parse_u_names(args.u_names)
    topo = load_chain_topology(args.chain)
    protocol = resolve_body_protocol(topo)
    if protocol != PROTO_AWG_BODY:
        raise SystemExit(
            f"export_client is not implemented for protocol {protocol!r}."
        )

    rc = export_wg_clients(args.chain, names)
    if rc != 0:
        return rc
    if topo.has_wrapper:
        from scripts.lib.common.wrappers import (
            export_clients as export_wrapper_clients,
            wrapper_protocol,
        )

        return export_wrapper_clients(
            args.chain, names, wrapper_protocol(topo)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
