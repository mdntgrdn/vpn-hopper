#!/usr/bin/env python3
"""Neighbor AWG server public keys manifest for secrets_push_peer_keys.yml."""
from __future__ import annotations

import argparse
import sys

import yaml

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.paths import env_paths, load_yaml


def write_peer_keys_manifest(chain_name: str) -> None:
    paths = env_paths(chain_settings(chain_name))
    if not paths.chain_generated.is_file():
        print(f"Missing {paths.chain_generated}", file=sys.stderr)
        sys.exit(1)
    if not paths.chain_runtime.is_file():
        print(f"Missing {paths.chain_runtime}", file=sys.stderr)
        sys.exit(1)

    gen = load_yaml(paths.chain_generated)
    hosts = [
        str(h)
        for h in (
            gen.get("chain_awg_chain_server_hosts")
            or gen.get("chain_awg_server_hosts")
            or gen.get("chain_ordered_hosts")
            or []
        )
    ]
    out = paths.work / "peer_public_keys_manifest.yml"
    out.parent.mkdir(parents=True, exist_ok=True)

    if not hosts:
        out.write_text(yaml.safe_dump({"host_peer_keys": {}}, sort_keys=False))
        print(f"Wrote {out} (0 hosts, no AWG servers)")
        return

    rt = load_yaml(paths.chain_runtime)
    ck = rt.get("chain_keys") or {}
    if not isinstance(ck, dict):
        print("chain_keys missing from chain_runtime.yml", file=sys.stderr)
        sys.exit(1)

    manifest: dict[str, list[dict[str, str]]] = {}
    n = len(hosts)
    for i, host in enumerate(hosts):
        peers: list[dict[str, str]] = []
        if n > 1 and i < n - 1:
            nxt = hosts[i + 1]
            pub = (ck.get(nxt) or {}).get("public_key", "").strip()
            if pub:
                peers.append({"peer": nxt, "public_key": pub})
        if n > 1 and i > 0:
            prv = hosts[i - 1]
            pub = (ck.get(prv) or {}).get("public_key", "").strip()
            if pub:
                peers.append({"peer": prv, "public_key": pub})
        if peers:
            manifest[host] = peers

    out.write_text(
        yaml.safe_dump({"host_peer_keys": manifest}, sort_keys=False, allow_unicode=True)
    )
    print(f"Wrote {out} ({len(manifest)} AWG server hosts)")


def main() -> None:
    parser = argparse.ArgumentParser()
    add_chain_cli(parser)
    args = parser.parse_args()
    write_peer_keys_manifest(args.chain)


if __name__ == "__main__":
    main()
