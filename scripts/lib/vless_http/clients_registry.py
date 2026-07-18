#!/usr/bin/env python3
"""Read/format the vless-http client registry (vless_clients.yml).

The registry lives on the wrapper host under <deploy_dir>/vless-http/ and is
pulled to the controller work area for listing, adding and removing users.
Shape (single wrapper host per chain):

    vless_http_clients:
      <wrapper_host>:
        - {username, slug, uuid, email}
"""
from __future__ import annotations

import json
import pathlib

import yaml

VLESS_CLIENTS_KEY = "vless_http_clients"


def load_registry(path: pathlib.Path) -> dict:
    if not path.is_file():
        return {VLESS_CLIENTS_KEY: {}}
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict) or not isinstance(data.get(VLESS_CLIENTS_KEY), dict):
        return {VLESS_CLIENTS_KEY: {}}
    return data


def clients_for_host(doc: dict, host: str) -> list[dict]:
    rows = (doc.get(VLESS_CLIENTS_KEY) or {}).get(host)
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def normalize_username(username: str) -> str:
    return (username or "").strip().casefold()


def find_username_row(username: str, rows: list[dict]) -> dict | None:
    want = normalize_username(username)
    if not want:
        return None
    for row in rows:
        u = row.get("username")
        if u and normalize_username(str(u)) == want:
            return row
    return None


def write_registry(path: pathlib.Path, host: str, rows: list[dict]) -> None:
    doc = load_registry(path)
    doc.setdefault(VLESS_CLIENTS_KEY, {})[host] = rows
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


def format_table(host: str, rows: list[dict]) -> str:
    lines = [f"wrapper: {host}", f"vless-http clients: {len(rows)}", ""]
    if not rows:
        lines.append("(empty)")
        return "\n".join(lines) + "\n"
    hdr = f"{'#':<4} {'username':<24} {'email':<28} uuid"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for i, row in enumerate(rows, 1):
        user = str(row.get("username") or "—")[:24]
        email = str(row.get("email") or "—")[:28]
        uid = str(row.get("uuid") or "—").strip()
        lines.append(f"{i:<4} {user:<24} {email:<28} {uid}")
    return "\n".join(lines) + "\n"


def format_output(host: str, rows: list[dict], fmt: str) -> str:
    payload = {VLESS_CLIENTS_KEY: {host: rows}}
    if fmt == "table":
        return format_table(host, rows)
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if fmt == "yaml":
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    raise ValueError(f"Unknown format: {fmt!r}")
