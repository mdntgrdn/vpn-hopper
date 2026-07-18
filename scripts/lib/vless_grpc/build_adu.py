#!/usr/bin/env python3
"""Build the `xray api adu` payload to hot-add vless-grpc users (no restart)."""
from __future__ import annotations

import json
import pathlib

from scripts.lib.common.paths import VLESS_GRPC_INBOUND_TAG


def adu_clients_from_batch(batch: list[dict]) -> list[dict]:
    """gRPC users carry no XTLS flow."""
    clients: list[dict] = []
    for row in batch:
        uid = str(row.get("uuid") or "").strip()
        if not uid:
            continue
        clients.append(
            {"id": uid, "email": str(row.get("email") or f"{uid}@vless-grpc")}
        )
    return clients


def build_adu_payload(
    *,
    listen_port: int,
    batch: list[dict],
    inbound_tag: str = VLESS_GRPC_INBOUND_TAG,
) -> dict:
    return {
        "inbounds": [
            {
                "tag": inbound_tag,
                "protocol": "vless",
                "listen": "0.0.0.0",
                "port": int(listen_port),
                "settings": {
                    "decryption": "none",
                    "clients": adu_clients_from_batch(batch),
                },
            }
        ]
    }


def write_adu_payload(
    out_dir: pathlib.Path,
    host: str,
    *,
    listen_port: int,
    batch: list[dict],
) -> pathlib.Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_adu_payload(listen_port=listen_port, batch=batch)
    out = out_dir / f"{host}.adu.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
