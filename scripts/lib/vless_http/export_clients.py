#!/usr/bin/env python3
"""Re-export .vless.txt/.json for existing vless-http client(s) by name."""
from __future__ import annotations

import sys

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.paths import cleanup_work_dir, env_paths
from scripts.lib.vless_http.client_export import export_client
from scripts.lib.vless_http.clients_registry import find_username_row
from scripts.lib.vless_http.fetch_clients import fetch_clients


def export_clients(
    chain: str, names: list[str], *, generate: bool = True
) -> int:
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
            print(
                f"No vless-http client named {name!r} on wrapper {host!r}.",
                file=sys.stderr,
            )
        return 1

    paths = env_paths(chain_settings(chain))
    print()
    for row in matched:
        out = export_client(chain, row)
        print(f"Client {row.get('username')!r} (vless-http)\n  {out}\n")

    cleanup_work_dir(paths)
    print(f"Exported {len(matched)} vless-http client(s) from {host!r}.")
    return 0
