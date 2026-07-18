#!/usr/bin/env python3
"""Add vless-grpc client(s) on the wrapper host: append registry, render, hot-add."""
from __future__ import annotations

import sys

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.paths import cleanup_work_dir, env_paths, load_yaml
from scripts.lib.vless_grpc.ansible_run import run_vless_grpc_playbook
from scripts.lib.vless_grpc.build_adu import write_adu_payload
from scripts.lib.vless_grpc.client_batch import build_vless_peer_batch
from scripts.lib.vless_grpc.client_export import export_client
from scripts.lib.vless_grpc.clients_registry import find_username_row, write_registry
from scripts.lib.vless_grpc.fetch_clients import fetch_clients
from scripts.lib.vless_grpc.render_config import render_wrapper_config

ADD_PLAYBOOK = "add_peer.yml"


def _validate_names(batch: list[dict], existing: list[dict], host: str) -> list[str]:
    errors: list[str] = []
    for peer in batch:
        name = peer["username"]
        if find_username_row(name, existing) is not None:
            errors.append(
                f"Cannot add {name!r}: a vless-grpc client with that name already "
                f"exists on wrapper {host!r}."
            )
    return errors


def add_clients(chain: str, names: list[str], *, generate: bool = True) -> int:
    if generate:
        from scripts.lib.wg.inventory import generate_wg_inventory

        generate_wg_inventory(chain)

    host, existing = fetch_clients(chain, generate=False)
    batch = build_vless_peer_batch(names)
    errors = _validate_names(batch, existing, host)
    if errors:
        for msg in errors:
            print(msg, file=sys.stderr)
        print(
            "List clients:  python3 scripts/list_clients.py --chain " + chain,
            file=sys.stderr,
        )
        return 1

    paths = env_paths(chain_settings(chain))
    listen_port = int(load_yaml(paths.chain_generated).get("chain_wrapper_listen_port") or 443)
    write_registry(paths.vless_clients, host, existing + batch)
    render_wrapper_config(chain)
    write_adu_payload(paths.vless_grpc_configs, host, listen_port=listen_port, batch=batch)

    rc = run_vless_grpc_playbook(
        ADD_PLAYBOOK,
        chain,
        extra_vars={"vless_wrapper_host": host, "vless_peer_batch": batch},
    )
    if rc != 0:
        return rc

    print()
    for peer in batch:
        out = export_client(chain, peer)
        print(f"Client {peer['username']!r} (vless-grpc)\n  {out}\n")

    cleanup_work_dir(paths)
    print(f"Added {len(batch)} vless-grpc client(s) on {host!r}.")
    return 0
