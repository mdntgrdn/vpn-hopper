#!/usr/bin/env python3
"""Read and format the AWG client registry (awg_clients.yml). Entry-only model."""
from __future__ import annotations

import json
import pathlib

import yaml

AWG_CLIENTS_KEY = "awg_wireguard_clients"


def load_awg_clients_document(path: pathlib.Path) -> dict:
    if not path.is_file():
        return {AWG_CLIENTS_KEY: {}}
    data = yaml.safe_load(path.read_text()) or {}
    return data if isinstance(data, dict) else {AWG_CLIENTS_KEY: {}}


def clients_for_host(doc: dict, host: str) -> list[dict]:
    m = doc.get(AWG_CLIENTS_KEY) or {}
    if not isinstance(m, dict):
        return []
    rows = m.get(host)
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


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


def list_awg_clients(awg_clients_path: pathlib.Path, entry_host: str) -> list[dict]:
    """Client rows registered on the chain entry node."""
    doc = load_awg_clients_document(awg_clients_path)
    return clients_for_host(doc, entry_host)


def write_awg_clients(
    path: pathlib.Path, entry_host: str, rows: list[dict]
) -> None:
    """Replace the entry host's rows in awg_clients.yml and write the file."""
    doc = load_awg_clients_document(path)
    clients_map = doc.get(AWG_CLIENTS_KEY)
    if not isinstance(clients_map, dict):
        clients_map = {}
        doc[AWG_CLIENTS_KEY] = clients_map
    clients_map[entry_host] = rows
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def format_table(host: str, rows: list[dict]) -> str:
    lines = [f"entry: {host}", f"clients: {len(rows)}", ""]
    if not rows:
        lines.append("(empty)")
        return "\n".join(lines) + "\n"
    hdr = f"{'#':<4} {'username':<24} {'allowed_ips':<20} public_key"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for i, row in enumerate(rows, 1):
        user = str(row.get("username") or row.get("comment") or "—")[:24]
        ips = str(row.get("allowed_ips") or "—")[:20]
        pk = str(row.get("public_key") or "—").strip()
        lines.append(f"{i:<4} {user:<24} {ips:<20} {pk}")
    return "\n".join(lines) + "\n"


def format_output(host: str, rows: list[dict], fmt: str) -> str:
    payload = {AWG_CLIENTS_KEY: {host: rows}}
    if fmt == "table":
        return format_table(host, rows)
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if fmt == "yaml":
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    raise ValueError(f"Unknown format: {fmt!r}")
