#!/usr/bin/env python3
"""Append a client to awg_clients.yml on the controller (called from add_peer playbook)."""
from __future__ import annotations

import argparse
import os
import sys

import yaml

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.paths import env_paths, load_yaml
from scripts.lib.wg.list_awg_clients import AWG_CLIENTS_KEY, find_username_row


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


def append_client(
    chain: str,
    entry_host: str,
    public_key: str,
    allowed_ips: str,
    *,
    private_key: str = "",
    username: str = "",
    comment: str = "",
) -> int:
    """0 ok, 1 duplicate, 2 error."""
    if not public_key or not allowed_ips:
        print("public_key and allowed_ips must not be empty.", file=sys.stderr)
        return 2

    dest = env_paths(chain_settings(chain)).awg_clients
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = yaml.safe_load(dest.read_text()) or {} if dest.is_file() else {}
    if not isinstance(data, dict):
        data = {}

    clients_map = data.setdefault(AWG_CLIENTS_KEY, {})
    if not isinstance(clients_map, dict):
        clients_map = {}
        data[AWG_CLIENTS_KEY] = clients_map

    lst = clients_map.setdefault(entry_host, [])
    if not isinstance(lst, list):
        lst = []
        clients_map[entry_host] = lst

    if username and find_username_row(username, lst):
        print(f"Client username={username.strip()!r} already exists for {entry_host}.", file=sys.stderr)
        return 1
    for row in lst:
        if isinstance(row, dict) and row.get("public_key") == public_key:
            print(f"Duplicate public_key for {entry_host}.", file=sys.stderr)
            return 1

    entry: dict = {"public_key": public_key}
    if private_key.strip():
        entry["private_key"] = private_key.strip()
    entry["allowed_ips"] = allowed_ips
    if username.strip():
        entry["username"] = username.strip()
    if comment.strip():
        entry["comment"] = comment.strip()
    lst.append(entry)
    dest.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Appended to {dest} for {entry_host!r}: {allowed_ips}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Append a client to awg_clients.yml")
    add_chain_cli(ap)
    ap.add_argument("--public-key", required=True)
    ap.add_argument("--allowed-ips", required=True)
    ap.add_argument("--comment", default="")
    args = ap.parse_args(argv)
    entry = _entry_host(args.chain)
    return append_client(
        args.chain,
        entry,
        args.public_key.strip(),
        args.allowed_ips.strip(),
        private_key=(os.environ.get("WG_PEER_PRIVATE_KEY") or "").strip(),
        username=(os.environ.get("WG_PEER_USERNAME") or "").strip(),
        comment=args.comment.strip(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
