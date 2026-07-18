#!/usr/bin/env python3
"""Add AWG client(s) on the chain entry: validate names, deploy peers, render .conf."""
from __future__ import annotations

import sys

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.paths import cleanup_work_dir, env_paths
from scripts.lib.wg.ansible_run import run_wg_playbook
from scripts.lib.wg.inventory import generate_wg_inventory
from scripts.lib.wg.list_awg_clients import find_username_row
from scripts.lib.wg.list_clients import fetch_clients
from scripts.lib.wg.peer_batch import build_wg_peer_batch
from scripts.lib.wg.render_client_conf import render_client_conf

ADD_PLAYBOOK = "add_peer.yml"


def _validate_names(batch: list[dict], existing: list[dict], entry: str) -> list[str]:
    errors: list[str] = []
    for peer in batch:
        name = peer["username"]
        if find_username_row(name, existing) is not None:
            errors.append(
                f"Cannot add {name!r}: a client with that name already exists on entry {entry!r}."
            )
    return errors


def add_clients(chain: str, names: list[str]) -> int:
    generate_wg_inventory(chain)
    batch = build_wg_peer_batch(names)

    entry, existing = fetch_clients(chain, generate=False)
    errors = _validate_names(batch, existing, entry)
    if errors:
        for msg in errors:
            print(msg, file=sys.stderr)
        print(
            "List clients:  python3 scripts/list_clients.py --chain " + chain,
            file=sys.stderr,
        )
        return 1

    rc = run_wg_playbook(
        ADD_PLAYBOOK,
        chain,
        extra_vars={"wg_entry_host": entry, "wg_peer_batch": batch},
    )
    if rc != 0:
        return rc

    paths = env_paths(chain_settings(chain))
    print()
    for peer in batch:
        out = render_client_conf(chain, peer["username"])
        print(f"Client {peer['username']!r} (AWG)\n  {out}\n")

    cleanup_work_dir(paths)
    print(f"Added {len(batch)} AWG client(s) on {entry!r}.")
    return 0
