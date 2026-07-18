#!/usr/bin/env python3
"""Render WG configs for roles/wg body deploy (entry-only awg_clients)."""
from __future__ import annotations

import argparse
import sys

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from scripts.lib.common.chains import load_chain_settings, load_chain_topology
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.paths import env_paths
from scripts.lib.common.topology import gateway_snat_source
from scripts.lib.wg.render_context import (
    AWG_TEMPLATES_DIR,
    build_chain_server_context,
    load_yaml_required,
    template_for_chain,
    wg_clients_for_host,
)


def _clients_map_entry_only(path, entry_host: str) -> dict[str, list[dict]]:
    if not path.is_file():
        return {entry_host: []}
    raw = yaml.safe_load(path.read_text()) or {}
    m = raw.get("awg_wireguard_clients") or {}
    if not isinstance(m, dict):
        return {entry_host: []}
    rows = m.get(entry_host, [])
    if not isinstance(rows, list):
        rows = []
    return {entry_host: [r for r in rows if isinstance(r, dict)]}


def render_wg_body_configs(
    chain_name: str,
    *,
    hosts: str = "",
) -> None:
    paths = env_paths(load_chain_settings(chain_name=chain_name))
    settings = load_chain_settings(chain_name=chain_name)
    topo = load_chain_topology(chain_name)
    chain_servers = topo.awg_chain_server_hosts
    if not chain_servers:
        print(f"Chain {chain_name!r} has no awg/server segments — skip AWG render.", file=sys.stderr)
        sys.exit(0)
    meta = topo.host_meta
    n = len(chain_servers)
    entry_host = topo.entry_host

    only = [h.strip() for h in hosts.split(",") if h.strip()]
    server_plan = [(i, h) for i, h in enumerate(chain_servers) if not only or h in only]

    keys_data = load_yaml_required(paths.chain_runtime)
    chain_keys = keys_data.get("chain_keys") or {}
    if not isinstance(chain_keys, dict):
        print("keys YAML requires a chain_keys key.", file=sys.stderr)
        sys.exit(1)

    clients_map = _clients_map_entry_only(paths.awg_clients, entry_host)

    env = Environment(
        loader=FileSystemLoader(str(AWG_TEMPLATES_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    output_dir = paths.awg_configs
    output_dir.mkdir(parents=True, exist_ok=True)

    base_port = int(settings["awg_base_port"])
    chain_deploy = str(settings["awg_chain_name"])
    rt = int(settings["routing_table"])
    tunnel_subnet = str(settings["tunnel_subnet"])
    wan = str(settings["wan_iface"])
    chain_client_subnet = str(settings.get("client_subnet") or topo.client_subnet)

    for i, hostname in server_plan:
        tpl_name = template_for_chain(i, n)
        template = env.get_template(tpl_name)
        ctx = build_chain_server_context(
            index=i,
            n=n,
            servers=chain_servers,
            meta=meta,
            chain_keys=chain_keys,
            awg_base_port=base_port,
            client_subnet=chain_client_subnet,
            tunnel_subnet=tunnel_subnet,
            wan_iface=wan,
            chain_name=chain_deploy,
            routing_table=rt,
        )
        if tpl_name == "entry.conf.j2" and hostname == entry_host:
            ctx["snat_source_ip"] = gateway_snat_source(topo, hostname)
        if tpl_name in ("entry.conf.j2", "final_solo.conf.j2") and hostname == entry_host:
            ctx["wg_clients"] = wg_clients_for_host(hostname, meta, clients_map)
        text = template.render(**ctx)
        (output_dir / f"{hostname}.conf").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render WG configs (roles/wg body)")
    add_chain_cli(parser)
    parser.add_argument(
        "--hosts",
        default="",
        help="Only these nodes (inventory names), comma-separated; default — entire chain",
    )
    args = parser.parse_args()
    render_wg_body_configs(args.chain, hosts=args.hosts)


if __name__ == "__main__":
    main()
