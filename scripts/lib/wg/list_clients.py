#!/usr/bin/env python3
"""Fetch the AWG client registry from chain entry and list/validate it."""
from __future__ import annotations

import sys

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.paths import env_paths, load_yaml
from scripts.lib.wg.ansible_run import run_wg_playbook
from scripts.lib.wg.inventory import generate_wg_inventory
from scripts.lib.wg.list_awg_clients import format_output, list_awg_clients

FETCH_PLAYBOOK = "fetch_clients.yml"


def _entry_host(chain: str) -> str:
    paths = env_paths(chain_settings(chain))
    gen = load_yaml(paths.chain_generated)
    host = str(gen.get("chain_entry_host") or "").strip()
    if host:
        return host
    hosts = gen.get("chain_ordered_hosts") or []
    if hosts:
        return str(hosts[0])
    print(f"Missing chain_entry_host in {paths.chain_generated}", file=sys.stderr)
    sys.exit(1)


def fetch_clients(chain: str, *, generate: bool = True) -> tuple[str, list[dict]]:
    """Run inventory (optional) + fetch playbook; return (entry_host, client rows)."""
    if generate:
        generate_wg_inventory(chain)
    entry = _entry_host(chain)
    rc = run_wg_playbook(FETCH_PLAYBOOK, chain, extra_vars={"wg_entry_host": entry})
    if rc != 0:
        print("Failed to fetch awg_clients from entry.", file=sys.stderr)
        sys.exit(rc)
    paths = env_paths(chain_settings(chain))
    return entry, list_awg_clients(paths.awg_clients, entry)


def list_clients(chain: str, *, fmt: str = "table", generate: bool = True) -> int:
    entry, rows = fetch_clients(chain, generate=generate)
    sys.stdout.write(format_output(entry, rows, fmt))
    return 0
