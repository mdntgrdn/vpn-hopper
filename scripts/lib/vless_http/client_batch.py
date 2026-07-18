#!/usr/bin/env python3
"""Map -u client names → vless_peer_batch for the vless-http add flow."""
from __future__ import annotations

import sys
import uuid as uuidlib

from scripts.lib.vless_http.vless import VLESS_FLOW_DEFAULT
from scripts.lib.wg.peer_batch import auto_peer_id, sanitize_slug


def client_email(slug: str) -> str:
    return f"{slug}@vless-http"


def build_vless_peer_batch(display_names: list[str]) -> list[dict[str, str]]:
    """List of {username, slug, uuid, email, flow}; slug from name (Latin) or auto."""
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
        batch.append(
            {
                "username": display_name,
                "slug": slug,
                "uuid": str(uuidlib.uuid4()),
                "email": client_email(slug),
                "flow": VLESS_FLOW_DEFAULT,
            }
        )
    return batch
