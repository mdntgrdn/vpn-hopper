#!/usr/bin/env python3
"""Render an AmneziaWG client .conf for a peer on the chain entry node."""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from scripts.lib.common.chains import load_chain_settings, load_chain_topology
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.paths import REPO_ROOT, env_paths, load_yaml
from scripts.lib.wg.list_awg_clients import (
    clients_for_host,
    find_username_row,
    load_awg_clients_document,
)
from scripts.lib.wg.peer_batch import sanitize_slug

ROLE_DEFAULTS = REPO_ROOT / "ansible" / "roles" / "wg" / "defaults" / "main.yml"
TEMPLATE = REPO_ROOT / "ansible" / "components" / "awg" / "templates" / "wg_client.conf.j2"


def client_conf_file_stem(username: str, slug: str) -> str:
    u = (username or "").strip()
    if not u:
        return slug
    for c in "/\\:\0\n\r\t":
        u = u.replace(c, "_")
    u = u.strip().strip(".")
    return u[:200] if u else slug


def _client_dns_default() -> str:
    d = load_yaml(ROLE_DEFAULTS)
    v = d.get("wg_client_dns")
    return str(v).strip() if v else "1.1.1.1"


def _entry_host(chain: str, paths) -> str:
    gen = load_yaml(paths.chain_generated)
    host = str(gen.get("chain_entry_host") or "").strip()
    if host:
        return host
    hosts = gen.get("chain_ordered_hosts") or []
    if hosts:
        return str(hosts[0])
    print(f"Missing chain_entry_host in {paths.chain_generated}", file=sys.stderr)
    sys.exit(1)


def render_client_conf(
    chain: str, username: str, *, output: str = ""
) -> pathlib.Path:
    display_username = (username or "").strip()
    if not display_username:
        print("Empty client username.", file=sys.stderr)
        sys.exit(2)

    settings = load_chain_settings(chain_name=chain)
    paths = env_paths(settings)
    topo = load_chain_topology(chain)
    entry = _entry_host(chain, paths)

    rows = clients_for_host(load_awg_clients_document(paths.awg_clients), entry)
    row = find_username_row(display_username, rows)
    if row is None:
        print(
            f"No AWG client named {display_username!r} on entry {entry!r}.",
            file=sys.stderr,
        )
        sys.exit(1)

    client_priv = str(row.get("private_key") or "").strip()
    if not client_priv:
        print(
            f"No private_key stored for {display_username!r} in awg_clients.yml.",
            file=sys.stderr,
        )
        sys.exit(1)

    client_addr = str(row.get("allowed_ips") or "").strip()
    if not client_addr:
        print(
            f"No allowed_ips for {display_username!r} in awg_clients.yml.",
            file=sys.stderr,
        )
        sys.exit(1)
    if "/" not in client_addr:
        client_addr = f"{client_addr}/32"

    slug = sanitize_slug(display_username) or display_username
    pub_ip = topo.host_meta.get(entry, {}).get("public_ip")
    if not pub_ip:
        print(f"Set public_ip for {entry} in chains.yaml.", file=sys.stderr)
        sys.exit(1)

    rt = load_yaml(paths.chain_runtime)
    ck = rt.get("chain_keys") or {}
    if not isinstance(ck, dict) or entry not in ck:
        print(f"Missing chain_keys[{entry}] in chain_runtime.yml.", file=sys.stderr)
        sys.exit(1)
    srv_pub = str(ck[entry].get("public_key", "")).strip()
    if not srv_pub:
        print(f"Empty server public_key for {entry}.", file=sys.stderr)
        sys.exit(1)

    base_port = int(settings["awg_base_port"])
    port = topo.awg_listen_port(entry, base_port)
    endpoint = f"{str(pub_ip).strip()}:{port}"

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE.parent)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    text = env.get_template(TEMPLATE.name).render(
        client_address=client_addr,
        client_private_key=client_priv,
        client_dns=_client_dns_default(),
        server_public_key=srv_pub,
        server_endpoint=endpoint,
        client_username=display_username,
    )

    stem = client_conf_file_stem(display_username, slug)
    out = pathlib.Path(output) if output.strip() else paths.clients_out / f"{stem}.conf"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="AmneziaWG client .conf for a peer on entry."
    )
    add_chain_cli(ap)
    ap.add_argument(
        "--username", required=True, help="Registered client username"
    )
    ap.add_argument("-o", "--output", default="", help="Output .conf path")
    args = ap.parse_args()
    render_client_conf(args.chain, args.username, output=args.output)


if __name__ == "__main__":
    main()
