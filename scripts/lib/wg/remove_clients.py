#!/usr/bin/env python3
"""Remove AWG client(s) on the chain entry: drop peers, syncconf, re-render."""
from __future__ import annotations

import sys

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.paths import cleanup_work_dir, env_paths
from scripts.lib.wg.ansible_run import run_wg_playbook
from scripts.lib.wg.inventory import generate_wg_inventory
from scripts.lib.wg.list_awg_clients import (
    find_username_row,
    write_awg_clients,
)
from scripts.lib.wg.list_clients import fetch_clients
from scripts.lib.wg.peer_batch import sanitize_slug
from scripts.lib.wg.render_client_conf import client_conf_file_stem

REMOVE_PLAYBOOK = "remove_peer.yml"


def _delete_export(chain: str, row: dict) -> None:
    paths = env_paths(chain_settings(chain))
    username = str(row.get("username") or "")
    stem = client_conf_file_stem(username, sanitize_slug(username))
    f = paths.clients_out / f"{stem}.conf"
    if f.is_file():
        f.unlink()


def remove_clients(
    chain: str, names: list[str], *, generate: bool = True
) -> int:
    if generate:
        generate_wg_inventory(chain)

    entry, existing = fetch_clients(chain, generate=False)

    matched: list[dict] = []
    missing: list[str] = []
    for name in names:
        row = find_username_row(name, existing)
        if row is None:
            missing.append(name)
        else:
            matched.append(row)
    if missing:
        for name in missing:
            print(
                f"No AWG client named {name!r} on entry {entry!r}.",
                file=sys.stderr,
            )
        print(
            "List clients:  python3 scripts/list_clients.py --chain " + chain,
            file=sys.stderr,
        )
        return 1

    pubkeys = [
        str(r.get("public_key")).strip()
        for r in matched
        if str(r.get("public_key") or "").strip()
    ]
    remaining = [r for r in existing if r not in matched]

    paths = env_paths(chain_settings(chain))
    write_awg_clients(paths.awg_clients, entry, remaining)

    rc = run_wg_playbook(
        REMOVE_PLAYBOOK,
        chain,
        extra_vars={"wg_entry_host": entry, "wg_remove_pubkeys": pubkeys},
    )
    if rc != 0:
        return rc

    for row in matched:
        _delete_export(chain, row)

    cleanup_work_dir(paths)
    print(f"Removed {len(matched)} AWG client(s) from {entry!r}.")
    return 0
