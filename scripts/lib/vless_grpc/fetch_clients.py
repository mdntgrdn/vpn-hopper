#!/usr/bin/env python3
"""Fetch the vless-grpc client registry from the wrapper host and list it."""
from __future__ import annotations

import sys

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.paths import env_paths, load_yaml
from scripts.lib.vless_grpc.ansible_run import run_vless_grpc_playbook
from scripts.lib.vless_grpc.clients_registry import (
    clients_for_host,
    format_output,
    load_registry,
)
from scripts.lib.wg.inventory import generate_wg_inventory

FETCH_PLAYBOOK = "fetch_clients.yml"


def wrapper_host(chain: str) -> str:
    paths = env_paths(chain_settings(chain))
    gen = load_yaml(paths.chain_generated)
    if not gen.get("chain_has_wrapper"):
        print(f"chains.{chain}: no wrapper defined.", file=sys.stderr)
        sys.exit(2)
    host = str(gen.get("chain_wrapper_host") or "").strip()
    if not host:
        print(f"Missing chain_wrapper_host in {paths.chain_generated}", file=sys.stderr)
        sys.exit(1)
    return host


def fetch_clients(chain: str, *, generate: bool = True) -> tuple[str, list[dict]]:
    """Run inventory (optional) + fetch playbook; return (wrapper_host, client rows)."""
    if generate:
        generate_wg_inventory(chain)
    host = wrapper_host(chain)
    rc = run_vless_grpc_playbook(FETCH_PLAYBOOK, chain, extra_vars={"vless_wrapper_host": host})
    if rc != 0:
        print("Failed to fetch vless_clients from wrapper host.", file=sys.stderr)
        sys.exit(rc)
    paths = env_paths(chain_settings(chain))
    return host, clients_for_host(load_registry(paths.vless_clients), host)


def list_clients(chain: str, *, fmt: str = "table", generate: bool = True) -> int:
    host, rows = fetch_clients(chain, generate=generate)
    sys.stdout.write(format_output(host, rows, fmt))
    return 0
