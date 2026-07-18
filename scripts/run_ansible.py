#!/usr/bin/env python3
"""
Deploy a chain by name. The body protocol is auto-resolved from chains.yaml.

  python3 scripts/run_ansible.py --chain my-chain

Only homogeneous AWG body chains are supported: every hop must be awg/server
and contain no other protocols. Mixed or VLESS chains are rejected.
"""
from __future__ import annotations

import argparse

from scripts.lib.common.chains import load_chain_topology, load_chains_document
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.protocol import PROTO_AWG_BODY, resolve_body_protocol
from scripts.lib.common.wrappers import deploy_wrapper, wrapper_protocol
from scripts.lib.wg.run_wg_body import deploy_wg_body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deploy a chain (auto-detects body protocol)"
    )
    add_chain_cli(parser)
    args = parser.parse_args(argv)

    doc = load_chains_document()
    topo = load_chain_topology(args.chain, doc=doc)
    protocol = resolve_body_protocol(topo)

    if protocol == PROTO_AWG_BODY:
        rc = deploy_wg_body(args.chain, doc=doc)
        if rc != 0:
            return rc
        if topo.has_wrapper:
            # Deploy the entry-node wrapper last, as a separate layer. The AWG
            # body playbook never references it.
            return deploy_wrapper(args.chain, wrapper_protocol(topo))
        return 0

    raise SystemExit(f"Body protocol {protocol!r} is not implemented yet.")


if __name__ == "__main__":
    raise SystemExit(main())
