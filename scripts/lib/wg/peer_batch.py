#!/usr/bin/env python3
"""Map -u client names → wg_peer_batch for the add_clients flow."""
from __future__ import annotations

import re
import secrets
import sys
from datetime import datetime, timezone


def sanitize_slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_.-]", "_", s.strip())
    return re.sub(r"^[_.-]+|[_.-]+$", "", s)


def auto_peer_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"peer-{ts}-{secrets.token_hex(3)}"


def build_wg_peer_batch(display_names: list[str]) -> list[dict[str, str]]:
    """List of {username, wg_peer_id}; slug from name (Latin) or auto peer-<ts>-<hex>."""
    batch: list[dict[str, str]] = []
    slugs_seen: set[str] = set()
    for display_name in display_names:
        cand_slug = sanitize_slug(display_name)
        slug = cand_slug or auto_peer_id()
        if slug in slugs_seen:
            print(
                f"Slug conflict {slug!r} for different names — use unique -u values.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        slugs_seen.add(slug)
        if cand_slug:
            sys.stderr.write(f"  {display_name!r} → slug {slug}\n")
        else:
            sys.stderr.write(
                f"  {display_name!r} → slug {slug} (auto: no Latin identifier derived)\n"
            )
        batch.append({"username": display_name, "wg_peer_id": slug})
    return batch


def parse_u_names(u_values: list[str]) -> list[str]:
    """Split each -u on commas; flatten, strip, drop empties, reject case-insensitive dups."""
    names: list[str] = []
    seen: set[str] = set()
    for raw in u_values:
        for part in str(raw).split(","):
            name = part.strip()
            if not name:
                continue
            key = name.casefold()
            if key in seen:
                print(f"Duplicate client name in -u: {name!r}.", file=sys.stderr)
                raise SystemExit(2)
            seen.add(key)
            names.append(name)
    if not names:
        print('No client names. Use -u "Name" or -u "A,B,C".', file=sys.stderr)
        raise SystemExit(2)
    return names
