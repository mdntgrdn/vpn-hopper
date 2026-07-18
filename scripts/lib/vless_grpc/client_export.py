#!/usr/bin/env python3
"""Write end-user vless-grpc export files: <name>.vless.txt (URI) + .vless.json."""
from __future__ import annotations

import json
import pathlib

from scripts.lib.common.chains import load_chain_settings
from scripts.lib.common.paths import env_paths, load_yaml
from scripts.lib.vless_grpc.vless import (
    SERVICE_NAME_DEFAULT,
    build_client_profile,
    build_vless_uri,
)


def _export_stem(username: str, slug: str) -> str:
    u = (username or "").strip()
    if not u:
        return slug
    for c in "/\\:\0\n\r\t":
        u = u.replace(c, "_")
    u = u.strip().strip(".")
    return (u[:200] or slug)


def export_client(chain: str, peer: dict) -> pathlib.Path:
    """Write export files for one vless-grpc client (peer batch row)."""
    settings = load_chain_settings(chain_name=chain)
    paths = env_paths(settings)
    gen = load_yaml(paths.chain_generated)

    server_name = str(gen.get("chain_wrapper_server_name") or "").strip()
    port = int(gen.get("chain_wrapper_listen_port") or 443)
    service_name = str(gen.get("chain_wrapper_service_name") or "").strip() or SERVICE_NAME_DEFAULT
    uuid = str(peer["uuid"]).strip()
    username = str(peer.get("username") or "").strip()
    slug = str(peer.get("slug") or username or uuid)

    uri = build_vless_uri(
        uuid=uuid, server_name=server_name, port=port, service_name=service_name
    )
    profile = build_client_profile(
        uuid=uuid, server_name=server_name, port=port, service_name=service_name
    )

    stem = _export_stem(username, slug)
    paths.clients_out.mkdir(parents=True, exist_ok=True)
    txt_path = paths.clients_out / f"{stem}.vless.txt"
    json_path = paths.clients_out / f"{stem}.vless.json"
    txt_path.write_text(
        f"# VLESS+gRPC client: {username or slug}\n"
        f"# Server: {server_name}:{port} (serviceName={service_name})\n\n{uri}\n",
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return txt_path
