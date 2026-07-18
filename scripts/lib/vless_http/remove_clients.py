#!/usr/bin/env python3
"""Remove vless-http client(s) from the wrapper host: rmu, drop from registry."""
from __future__ import annotations

import sys

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.paths import cleanup_work_dir, env_paths
from scripts.lib.vless_http.ansible_run import run_vless_http_playbook
from scripts.lib.vless_http.client_export import _export_stem
from scripts.lib.vless_http.clients_registry import find_username_row, write_registry
from scripts.lib.vless_http.fetch_clients import fetch_clients
from scripts.lib.vless_http.render_config import render_wrapper_config

REMOVE_PLAYBOOK = "remove_peer.yml"


def _delete_exports(chain: str, row: dict) -> None:
    paths = env_paths(chain_settings(chain))
    stem = _export_stem(str(row.get("username") or ""), str(row.get("slug") or ""))
    for suffix in (".vless.txt", ".vless.json"):
        f = paths.clients_out / f"{stem}{suffix}"
        if f.is_file():
            f.unlink()


def remove_clients(chain: str, names: list[str], *, generate: bool = True) -> int:
    if generate:
        from scripts.lib.wg.inventory import generate_wg_inventory

        generate_wg_inventory(chain)

    host, existing = fetch_clients(chain, generate=False)

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
            print(f"No vless-http client named {name!r} on wrapper {host!r}.", file=sys.stderr)
        return 1

    emails = [str(r.get("email")) for r in matched if r.get("email")]
    remaining = [r for r in existing if r not in matched]

    paths = env_paths(chain_settings(chain))
    write_registry(paths.vless_clients, host, remaining)
    render_wrapper_config(chain)

    rc = run_vless_http_playbook(
        REMOVE_PLAYBOOK,
        chain,
        extra_vars={"vless_wrapper_host": host, "vless_rmu_emails": emails},
    )
    if rc != 0:
        return rc

    for row in matched:
        _delete_exports(chain, row)

    cleanup_work_dir(paths)
    print(f"Removed {len(matched)} vless-http client(s) from {host!r}.")
    return 0
