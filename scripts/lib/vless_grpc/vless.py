#!/usr/bin/env python3
"""VLESS+TLS over gRPC (vless-grpc) wrapper helpers.

The wrapper is a standalone Xray container co-located with the AWG entry node.
It terminates VLESS over TLS+gRPC on the public port and forwards every client
connection out via a ``freedom`` outbound marked with the chain ``routing_table``
fwmark, so traffic enters the existing AWG entry routing table and the tunnel.

gRPC transport does not use the XTLS ``flow`` (Vision); users carry no flow.
A ``serviceName`` (gRPC service path) must match on server and client.

Certificate storage (when cert_file/key_file are not given in chains.yaml):
  <deploy_dir>/vless-grpc/letsencrypt/live/<server_name>/fullchain.pem
  <deploy_dir>/vless-grpc/letsencrypt/live/<server_name>/privkey.pem
This directory is volume-mounted into the wrapper container at the same path.
"""
from __future__ import annotations

from urllib.parse import quote, urlencode

# gRPC runs over HTTP/2 only.
SERVER_ALPN_DEFAULT = ["h2"]
CLIENT_ALPN_DEFAULT = ["h2"]
SERVICE_NAME_DEFAULT = "grpc"


def wrapper_server_name(cfg: dict) -> str:
    return str(cfg.get("server_name") or cfg.get("sni") or "").strip()


def wrapper_listen_port(cfg: dict) -> int:
    return int(cfg.get("listen_port") or 443)


def wrapper_service_name(cfg: dict) -> str:
    return str(cfg.get("service_name") or "").strip() or SERVICE_NAME_DEFAULT


def wrapper_server_alpn(cfg: dict) -> list[str]:
    # gRPC requires h2; alpn is not user-tunable for this transport.
    return list(SERVER_ALPN_DEFAULT)


def letsencrypt_dir(deploy_dir: str) -> str:
    return f"{deploy_dir.rstrip('/')}/vless-grpc/letsencrypt"


def wrapper_cert_file(cfg: dict, *, deploy_dir: str) -> str:
    explicit = str(cfg.get("cert_file") or "").strip()
    if explicit:
        return explicit
    sn = wrapper_server_name(cfg)
    return f"{letsencrypt_dir(deploy_dir)}/live/{sn}/fullchain.pem" if sn else ""


def wrapper_key_file(cfg: dict, *, deploy_dir: str) -> str:
    explicit = str(cfg.get("key_file") or "").strip()
    if explicit:
        return explicit
    sn = wrapper_server_name(cfg)
    return f"{letsencrypt_dir(deploy_dir)}/live/{sn}/privkey.pem" if sn else ""


def wrapper_use_certbot(cfg: dict) -> bool:
    """True when no explicit cert/key are given — issue a Let's Encrypt cert."""
    return not str(cfg.get("cert_file") or "").strip() and not str(
        cfg.get("key_file") or ""
    ).strip()


def build_vless_uri(
    *,
    uuid: str,
    server_name: str,
    port: int,
    service_name: str,
    alpn: list[str] | None = None,
) -> str:
    params: dict[str, str] = {
        "encryption": "none",
        "security": "tls",
        "sni": server_name,
        "fp": "chrome",
        "type": "grpc",
        "serviceName": service_name,
        "mode": "gun",
    }
    used_alpn = alpn if alpn else CLIENT_ALPN_DEFAULT
    if used_alpn:
        params["alpn"] = ",".join(used_alpn)
    query = urlencode({k: v for k, v in params.items() if v})
    return f"vless://{quote(uuid, safe='')}@{server_name}:{port}?{query}"


def build_client_profile(
    *,
    uuid: str,
    server_name: str,
    port: int,
    service_name: str,
    alpn: list[str] | None = None,
    tag: str = "proxy",
) -> dict:
    """Minimal Xray client outbound profile for a vless-grpc user."""
    user: dict = {"id": uuid, "encryption": "none"}
    tls_settings: dict = {"serverName": server_name, "fingerprint": "chrome"}
    used_alpn = alpn if alpn else CLIENT_ALPN_DEFAULT
    if used_alpn:
        tls_settings["alpn"] = used_alpn
    return {
        "log": {"loglevel": "warning"},
        "outbounds": [
            {
                "tag": tag,
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {"address": server_name, "port": port, "users": [user]}
                    ]
                },
                "streamSettings": {
                    "network": "grpc",
                    "security": "tls",
                    "tlsSettings": tls_settings,
                    "grpcSettings": {
                        "serviceName": service_name,
                        "multiMode": False,
                    },
                },
            }
        ],
    }
