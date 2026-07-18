#!/usr/bin/env python3
"""
Add client(s) on the chain entry node.

  python3 scripts/add_clients.py --chain awg-3hop -u "Alice,Bob"
  python3 scripts/add_clients.py --chain awg-3hop -u "Alice" -u "Bob,Carol"

Names are listed inside -u, comma-separated; -u may be repeated.
Creates an AWG peer (clients/<chain>/<name>.conf). When the chain defines a
wrapper (vless-http or vless-grpc), the same names are also created on the
wrapper (clients/<chain>/<name>.vless.txt).
"""
from __future__ import annotations

import argparse

from scripts.lib.common.chains import load_chain_topology
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.protocol import PROTO_AWG_BODY, resolve_body_protocol
from scripts.lib.wg.add_clients import add_clients as add_wg_clients
from scripts.lib.wg.peer_batch import parse_u_names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="add_clients",
        description="Add client(s) on the chain entry; dispatched by body protocol.",
        usage='%(prog)s --chain NAME -u "A,B,C" [-u "…"]',
    )
    add_chain_cli(ap)
    ap.add_argument(
        "-u",
        dest="u_names",
        action="append",
        required=True,
        metavar="NAMES",
        help='Client name(s), comma-separated; -u may be repeated.',
    )
    args = ap.parse_args(argv)

    names = parse_u_names(args.u_names)
    topo = load_chain_topology(args.chain)
    protocol = resolve_body_protocol(topo)
    if protocol != PROTO_AWG_BODY:
        raise SystemExit(f"add_clients is not implemented for protocol {protocol!r}.")

    rc = add_wg_clients(args.chain, names)
    if rc != 0:
        return rc
    if topo.has_wrapper:
        from scripts.lib.common.wrappers import (
            add_clients as add_wrapper_clients,
            wrapper_protocol,
        )

        return add_wrapper_clients(args.chain, names, wrapper_protocol(topo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
