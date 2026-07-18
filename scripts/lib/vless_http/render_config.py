#!/usr/bin/env python3
"""Render the vless-http wrapper Xray config (config.hybrid.json.j2).

Inbound: VLESS over TLS on the wrapper public port.
Outbound: freedom with sockopt.mark = chain routing_table → AWG entry fwmark
table → tunnel. Plus a localhost HandlerService API inbound for hot add/remove.
"""
from __future__ import annotations

import argparse
import json
import sys

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from scripts.lib.common.chains import load_chain_settings
from scripts.lib.common.cli import add_chain_cli
from scripts.lib.common.paths import (
    REPO_ROOT,
    VLESS_HTTP_API_PORT_DEFAULT,
    VLESS_HTTP_INBOUND_TAG,
    env_paths,
    load_yaml,
)
from scripts.lib.vless_http.clients_registry import clients_for_host, load_registry
from scripts.lib.vless_http.vless import (
    VLESS_FLOW_DEFAULT,
    wrapper_cert_file,
    wrapper_key_file,
)

VLESS_HTTP_TEMPLATES_DIR = (
    REPO_ROOT / "ansible" / "components" / "vless-http" / "templates"
)
HYBRID_TEMPLATE = "config.hybrid.json.j2"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(VLESS_HTTP_TEMPLATES_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tojson"] = lambda val: json.dumps(val, ensure_ascii=False)
    return env


def _users(rows: list[dict]) -> list[dict]:
    users: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        uid = str(row.get("uuid") or "").strip()
        if not uid or uid in seen:
            continue
        seen.add(uid)
        email = str(row.get("email") or f"{uid}@vless-http").strip()
        user: dict = {"id": uid, "email": email}
        flow = str(row.get("flow") or VLESS_FLOW_DEFAULT).strip()
        if flow:
            user["flow"] = flow
        users.append(user)
    return users


def build_render_context(chain: str) -> dict:
    settings = load_chain_settings(chain_name=chain)
    paths = env_paths(settings)
    gen = load_yaml(paths.chain_generated)
    if not gen.get("chain_has_wrapper"):
        print(f"chains.{chain}: no wrapper defined — nothing to render.", file=sys.stderr)
        sys.exit(2)

    deploy_dir = str(settings["deploy_dir"])
    routing_table = int(settings["routing_table"])
    cfg = {
        "server_name": gen.get("chain_wrapper_server_name"),
        "listen_port": gen.get("chain_wrapper_listen_port"),
        "alpn": gen.get("chain_wrapper_alpn"),
        "cert_file": gen.get("chain_wrapper_cert_file"),
        "key_file": gen.get("chain_wrapper_key_file"),
    }

    host = str(gen.get("chain_wrapper_host"))
    rows = clients_for_host(load_registry(paths.vless_clients), host)

    return {
        "listen_port": int(cfg["listen_port"] or 443),
        "inbound_tag": VLESS_HTTP_INBOUND_TAG,
        "clients": _users(rows),
        "tls_cert_file": wrapper_cert_file(cfg, deploy_dir=deploy_dir),
        "tls_key_file": wrapper_key_file(cfg, deploy_dir=deploy_dir),
        "tls_alpn": cfg["alpn"] or ["h2", "http/1.1"],
        "routing_mark": routing_table,
        "xray_api_port": VLESS_HTTP_API_PORT_DEFAULT,
    }


def render_config_text(ctx: dict) -> str:
    text = _env().get_template(HYBRID_TEMPLATE).render(**ctx)
    json.loads(text)  # validate
    return text + "\n"


def render_wrapper_config(chain: str) -> str:
    settings = load_chain_settings(chain_name=chain)
    paths = env_paths(settings)
    gen = load_yaml(paths.chain_generated)
    host = str(gen.get("chain_wrapper_host"))
    ctx = build_render_context(chain)
    paths.vless_http_configs.mkdir(parents=True, exist_ok=True)
    out = paths.vless_http_configs / f"{host}.json"
    out.write_text(render_config_text(ctx), encoding="utf-8")
    print(f"Wrote {out}")
    return str(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render vless-http wrapper Xray config")
    add_chain_cli(ap)
    args = ap.parse_args()
    render_wrapper_config(args.chain)


if __name__ == "__main__":
    main()
