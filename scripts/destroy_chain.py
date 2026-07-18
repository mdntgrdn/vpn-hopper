#!/usr/bin/env python3
"""
Destroy a chain by name. The body protocol is auto-resolved from chains.yaml.

  python3 scripts/destroy_chain.py --chain my-chain
  python3 scripts/destroy_chain.py --chain my-chain --yes

Removes the AWG container(s), Docker image and deploy directory on every node,
then deletes the local chain workspace and exported client configs.
Only homogeneous AWG body chains are supported.
"""
from __future__ import annotations

import argparse

from scripts.lib.common.chains import load_chain_topology, load_chains_document
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.protocol import PROTO_AWG_BODY, resolve_body_protocol
from scripts.lib.wg.destroy_chain import destroy_wg_body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Destroy a chain (auto-detects body protocol)"
    )
    add_chain_cli(parser)
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Do not prompt for confirmation.",
    )
    args = parser.parse_args(argv)

    doc = load_chains_document()
    topo = load_chain_topology(args.chain, doc=doc)
    protocol = resolve_body_protocol(topo)

    if protocol == PROTO_AWG_BODY:
        return destroy_wg_body(args.chain, assume_yes=args.yes, doc=doc)

    raise SystemExit(f"Body protocol {protocol!r} is not implemented yet.")


if __name__ == "__main__":
    raise SystemExit(main())
