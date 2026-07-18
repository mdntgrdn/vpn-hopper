#!/usr/bin/env python3
"""
List AWG clients registered on the chain entry node.

  python3 scripts/list_clients.py --chain awg-3hop
  python3 scripts/list_clients.py --chain awg-3hop --format json
"""
from __future__ import annotations

import argparse

from scripts.lib.common.chains import load_chain_topology
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.protocol import PROTO_AWG_BODY, resolve_body_protocol
from scripts.lib.wg.list_clients import list_clients as list_wg_clients


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="list_clients",
        description="List clients on chain entry; dispatched by body protocol",
    )
    add_chain_cli(ap)
    ap.add_argument(
        "--format",
        dest="fmt",
        choices=["table", "json", "yaml"],
        default="table",
    )
    args = ap.parse_args(argv)
    topo = load_chain_topology(args.chain)
    protocol = resolve_body_protocol(topo)
    if protocol != PROTO_AWG_BODY:
        raise SystemExit(
            f"list_clients is not implemented for protocol {protocol!r}."
        )

    rc = list_wg_clients(args.chain, fmt=args.fmt)
    if rc != 0:
        return rc
    if topo.has_wrapper:
        from scripts.lib.common.wrappers import (
            list_clients as list_wrapper_clients,
            wrapper_protocol,
        )

        print()
        return list_wrapper_clients(
            args.chain, wrapper_protocol(topo), fmt=args.fmt, generate=False
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
