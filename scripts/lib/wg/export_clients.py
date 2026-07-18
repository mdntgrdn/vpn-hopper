#!/usr/bin/env python3
"""Re-export .conf for existing AWG client(s) straight from awg_clients.yml."""
from __future__ import annotations

import sys

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.paths import cleanup_work_dir, env_paths
from scripts.lib.wg.ansible_run import run_wg_playbook
from scripts.lib.wg.inventory import generate_wg_inventory
from scripts.lib.wg.list_awg_clients import find_username_row
from scripts.lib.wg.list_clients import fetch_clients
from scripts.lib.wg.render_client_conf import render_client_conf

EXPORT_PLAYBOOK = "export_client.yml"


def export_clients(
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
        return 1

    # Pull entry node keys so chain_runtime.yml has the server public key and
    # endpoint needed to render the client .conf (client keys live in registry).
    rc = run_wg_playbook(
        EXPORT_PLAYBOOK, chain, extra_vars={"wg_entry_host": entry}
    )
    if rc != 0:
        return rc

    paths = env_paths(chain_settings(chain))
    print()
    for row in matched:
        username = str(row.get("username") or "")
        out = render_client_conf(chain, username)
        print(f"Client {username!r} (AWG)\n  {out}\n")

    cleanup_work_dir(paths)
    print(f"Exported {len(matched)} AWG client(s) from {entry!r}.")
    return 0
