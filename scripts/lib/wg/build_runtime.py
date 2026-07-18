#!/usr/bin/env python3
"""Merge AWG node keys from .work/artifacts into chain_runtime.yml (body deploy)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from scripts.lib.common.chains import chain_settings, load_chain_topology
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.paths import env_paths, load_yaml


def _load_existing_runtime(output: Path) -> dict[str, dict[str, str]]:
    if not output.is_file():
        return {}
    data = yaml.safe_load(output.read_text()) or {}
    if not isinstance(data, dict):
        return {}
    chain_keys = data.get("chain_keys") or {}
    return chain_keys if isinstance(chain_keys, dict) else {}


def _ingest_node_keys(chain_keys: dict, artifacts: Path) -> None:
    for sub in sorted(artifacts.iterdir()):
        if not sub.is_dir() or sub.name == "wg_clients":
            continue
        priv_file = sub / "private.key"
        pub_file = sub / "public.key"
        if priv_file.is_file() and pub_file.is_file():
            chain_keys[sub.name] = {
                "private_key": priv_file.read_text().strip(),
                "public_key": pub_file.read_text().strip(),
            }


def _merge_neighbor_public_keys(chain_keys: dict, entry_dir: Path) -> None:
    """Neighbor (next/prev hop) public keys from entry's awg/peers/ mirror."""
    peers_dir = entry_dir / "peers"
    if not peers_dir.is_dir():
        return
    for key_file in sorted(peers_dir.glob("*_public.key")):
        peer = key_file.name[: -len("_public.key")]
        pub = key_file.read_text().strip()
        if not peer or not pub:
            continue
        entry = dict(chain_keys.get(peer) or {})
        entry.setdefault("public_key", pub)
        chain_keys[peer] = entry


def _entry_host(paths) -> str:
    gen = load_yaml(paths.chain_generated)
    host = str(gen.get("chain_entry_host") or "").strip()
    if host:
        return host
    hosts = gen.get("chain_ordered_hosts") or []
    if hosts:
        return str(hosts[0])
    print(f"Missing chain_entry_host in {paths.chain_generated}", file=sys.stderr)
    sys.exit(1)


def build_chain_runtime(chain_name: str, *, client_pull: bool = False) -> None:
    settings = chain_settings(chain_name)
    paths = env_paths(settings)
    artifacts = paths.artifacts
    output = paths.chain_runtime

    if not artifacts.is_dir():
        print(f"artifacts dir missing: {artifacts}", file=sys.stderr)
        sys.exit(1)

    chain_keys = _load_existing_runtime(output)
    _ingest_node_keys(chain_keys, artifacts)

    if client_pull:
        entry = _entry_host(paths)
        if entry not in chain_keys or not chain_keys[entry].get("private_key"):
            print(
                f"Missing AWG node keys for entry {entry!r}. Pull entry runtime first.",
                file=sys.stderr,
            )
            sys.exit(1)
        _merge_neighbor_public_keys(chain_keys, artifacts / entry)
    else:
        topo = load_chain_topology(chain_name)
        missing = [h for h in topo.awg_deploy_hosts() if h not in chain_keys]
        if missing:
            print(
                f"Missing AWG keys for: {', '.join(missing)}. Run bootstrap plays first.",
                file=sys.stderr,
            )
            sys.exit(1)

    if not chain_keys:
        print(f"No AWG artifacts under {artifacts}/.", file=sys.stderr)
        sys.exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump({"chain_keys": chain_keys}, sort_keys=False, allow_unicode=True)
    )
    mode = ", client-pull" if client_pull else ""
    print(f"Wrote {output} (awg={len(chain_keys)}, chain={paths.chain_name!r}{mode})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build chain_runtime.yml from AWG node keys")
    add_chain_cli(parser)
    parser.add_argument(
        "--client-pull",
        action="store_true",
        help="Client ops: require only entry node keys; neighbor pubkeys from entry awg/peers/.",
    )
    args = parser.parse_args()
    build_chain_runtime(args.chain, client_pull=args.client_pull)


if __name__ == "__main__":
    main()
