#!/usr/bin/env python3
"""Generate inventory for roles/wg body deploy (homogeneous AWG)."""
from __future__ import annotations

import argparse
import shutil
import sys

import yaml

from scripts.lib.common.chains import (
    chain_settings,
    load_chain_entry,
    load_chains_document,
)
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.paths import (
    REPO_ROOT,
    ansible_group_name,
    chain_params_for_generated,
    ensure_work_dirs,
    env_paths,
    refresh_chain_workspace,
)
from scripts.lib.common.topology import (
    awg_position_for_host,
    build_chain_topology,
)


def _ansible_connect_vars(row: dict) -> dict:
    entry = dict(row)
    host = entry.pop("host", None)
    if host:
        entry["ansible_host"] = host
    user = entry.pop("user", None)
    if user:
        entry["ansible_user"] = user
    key = entry.pop("ssh_private_key_file", None)
    if key:
        entry["ansible_ssh_private_key_file"] = key
    entry.pop("_inventory_name", None)
    return entry


def _write_host_vars(host_vars_dir, topo, hostnames: list[str]) -> None:
    _ = (topo, hostnames)
    if host_vars_dir.is_dir():
        shutil.rmtree(host_vars_dir)
    host_vars_dir.mkdir(parents=True)


def _wrapper_generated(topo) -> dict:
    """chain_generated keys describing the entry-node protocol wrapper (if any)."""
    cfg = topo.wrapper_config()
    if not cfg:
        return {"chain_has_wrapper": False, "chain_wrapper_host": ""}
    cert_file = str(cfg.get("cert_file") or "").strip()
    key_file = str(cfg.get("key_file") or "").strip()
    alpn = cfg.get("alpn")
    if isinstance(alpn, str):
        alpn = [s.strip() for s in alpn.split(",") if s.strip()]
    elif isinstance(alpn, list):
        alpn = [str(s).strip() for s in alpn if str(s).strip()]
    else:
        alpn = ["http/1.1"]
    return {
        "chain_has_wrapper": True,
        "chain_wrapper_host": topo.wrapper_host,
        "chain_wrapper_protocol": str(cfg.get("protocol")),
        "chain_wrapper_listen_port": int(cfg.get("listen_port") or 443),
        "chain_wrapper_server_name": str(cfg.get("server_name")),
        "chain_wrapper_service_name": str(cfg.get("service_name") or "").strip(),
        "chain_wrapper_alpn": alpn,
        "chain_wrapper_cert_file": cert_file,
        "chain_wrapper_key_file": key_file,
        "chain_wrapper_use_certbot": not (cert_file or key_file),
    }


def _assert_homogeneous_awg_body(topo) -> None:
    if not topo.is_awg_chain:
        print(f"Chain {topo.chain_name!r} has no AWG body.", file=sys.stderr)
        sys.exit(2)
    bad = [h for h in topo.path_hosts if not topo.has_awg_server(h)]
    if bad:
        print(
            f"Chain {topo.chain_name!r} is not homogeneous AWG — hops without awg/server: "
            f"{', '.join(bad)}.",
            file=sys.stderr,
        )
        sys.exit(2)


def generate_wg_inventory(chain_name: str) -> None:
    if (
        not (REPO_ROOT / "chains.yaml").is_file()
        and not (REPO_ROOT / "chains.yaml.example").is_file()
    ):
        print("Create chains.yaml in the repo root.", file=sys.stderr)
        sys.exit(1)

    doc = load_chains_document()
    entry = load_chain_entry(chain_name, doc=doc)
    topo = build_chain_topology(chain_name=chain_name, entry=entry, doc=doc)
    _assert_homogeneous_awg_body(topo)

    names = topo.path_hosts
    rows = [
        {**dict(topo.host_meta[hop.host]), "_inventory_name": hop.host}
        for hop in topo.path
    ]
    settings = chain_settings(chain_name, doc=doc)
    paths = env_paths(settings)
    refresh_chain_workspace(paths)
    group = ansible_group_name(settings)

    hosts_block: dict = {}
    for row in rows:
        inv_name = row.pop("_inventory_name")
        hosts_block[inv_name] = _ansible_connect_vars(row)

    inv = {"all": {"children": {group: {"hosts": hosts_block}}}}
    paths.chain_root.mkdir(parents=True, exist_ok=True)
    ensure_work_dirs(paths)
    paths.inventory_yml.write_text(yaml.safe_dump(inv, sort_keys=False, allow_unicode=True))
    _write_host_vars(paths.host_vars_dir, topo, names)

    entry_host = topo.entry_host
    awg_positions = {
        hop.host: awg_position_for_host(topo, hop.host)
        for hop in topo.path
        if awg_position_for_host(topo, hop.host)
    }
    generated = {
        "chain_body_protocol": "awg",
        "chain_ordered_hosts": names,
        "chain_length": len(names),
        "chain_awg_position_by_host": awg_positions,
        "chain_awg_server_hosts": topo.awg_server_hosts,
        "chain_awg_chain_server_hosts": topo.awg_chain_server_hosts,
        "chain_awg_deploy_hosts": topo.awg_deploy_hosts(),
        "chain_entry_host": entry_host,
        "chain_exit_host": topo.exit_host,
        "chain_is_awg": True,
        **_wrapper_generated(topo),
        **chain_params_for_generated(settings),
    }
    paths.chain_generated.write_text(yaml.safe_dump(generated, sort_keys=False, allow_unicode=True))

    print(f"chain: {chain_name!r} (roles/wg)")
    print(f"Wrote {paths.inventory_yml} (group {group!r})")
    print(f"Wrote {paths.host_vars_dir}/")
    print(f"AWG servers: {topo.awg_server_hosts}")
    print(f"Entry: {entry_host}  Exit: {topo.exit_host}")
    if topo.has_wrapper:
        wc = topo.wrapper_config() or {}
        print(
            f"Wrapper: {wc.get('protocol')} on {topo.wrapper_host} "
            f"({wc.get('server_name')}:{wc.get('listen_port')})"
        )
    print(f"Wrote {paths.chain_generated}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate inventory for roles/wg deploy")
    add_chain_cli(parser)
    args = parser.parse_args()
    generate_wg_inventory(args.chain)


if __name__ == "__main__":
    main()
