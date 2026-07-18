"""Jinja2 context builders for AWG body chain configs."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from scripts.lib.common.paths import REPO_ROOT
from scripts.lib.common.tunnels import tunnel_cidr, tunnel_ipv4

AWG_TEMPLATES_DIR = REPO_ROOT / "ansible" / "components" / "awg" / "templates"


def load_yaml_required(path: Path) -> dict:
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    return yaml.safe_load(path.read_text()) or {}


def template_for_chain(index: int, n: int) -> str:
    if n == 1:
        return "final_solo.conf.j2"
    if index == 0:
        return "entry.conf.j2"
    if index == n - 1:
        return "final.conf.j2"
    return "middle.conf.j2"


def public_ip(meta: dict, host: str) -> str:
    ip = meta.get(host, {}).get("public_ip")
    if not ip:
        print(f"Set public_ip for host {host} in chains.yaml.", file=sys.stderr)
        sys.exit(1)
    return str(ip)


def normalize_wg_clients(rows: list[dict]) -> list[dict]:
    norm: list[dict] = []
    for r in rows:
        pk = r.get("public_key")
        ips = r.get("allowed_ips")
        if not pk or not ips:
            continue
        item = {"public_key": str(pk).strip(), "allowed_ips": str(ips).strip()}
        if r.get("username"):
            item["username"] = str(r["username"]).strip()
        if r.get("comment"):
            item["comment"] = str(r["comment"]).strip()
        if r.get("persistent_keepalive") is not None:
            item["persistent_keepalive"] = r["persistent_keepalive"]
        norm.append(item)
    return norm


def wg_clients_for_host(hostname: str, meta: dict, clients_map: dict) -> list[dict]:
    file_rows = clients_map.get(hostname, []) or []
    return normalize_wg_clients(file_rows)


def build_chain_server_context(
    *,
    index: int,
    n: int,
    servers: list[str],
    meta: dict[str, dict],
    chain_keys: dict[str, dict[str, str]],
    awg_base_port: int,
    client_subnet: str,
    tunnel_subnet: str,
    wan_iface: str,
    chain_name: str,
    routing_table: int,
) -> dict:
    name = servers[index]
    if name not in chain_keys:
        print(f"Missing keys for {name} in chain_runtime.yml.", file=sys.stderr)
        sys.exit(1)

    priv = chain_keys[name]["private_key"]
    ctx: dict = {
        "tunnel_address": tunnel_cidr(tunnel_subnet, index + 1),
        "listen_port": awg_base_port + index,
        "private_key": priv,
        "exit_tunnel_ip": tunnel_ipv4(tunnel_subnet, n),
        "client_subnet": client_subnet,
        "tunnel_subnet": tunnel_subnet,
        "wan_iface": wan_iface,
        "awg_chain_name": chain_name,
        "routing_table": routing_table,
        "wg_clients": [],
    }

    if n == 1:
        return ctx

    if index == 0:
        next_h = servers[1]
        ctx["peer_up_public_key"] = chain_keys[next_h]["public_key"]
        ctx["upstream_endpoint"] = f"{public_ip(meta, next_h)}:{awg_base_port + 1}"
        return ctx

    if index == n - 1:
        prev_h = servers[n - 2]
        ctx["peer_down_public_key"] = chain_keys[prev_h]["public_key"]
        ctx["downstream_tunnel_ip"] = tunnel_ipv4(tunnel_subnet, n - 1)
        return ctx

    nxt, prv = servers[index + 1], servers[index - 1]
    ctx["peer_down_public_key"] = chain_keys[nxt]["public_key"]
    ctx["peer_up_public_key"] = chain_keys[prv]["public_key"]
    ctx["peer_up_tunnel_ip"] = tunnel_ipv4(tunnel_subnet, index)
    ctx["downstream_endpoint"] = f"{public_ip(meta, nxt)}:{awg_base_port + index + 1}"
    return ctx
