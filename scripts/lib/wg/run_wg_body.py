#!/usr/bin/env python3
"""Deploy a homogeneous AWG (WG) body chain via ansible/roles/wg/."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import yaml

from typing import Any

from scripts.lib.common.chains import chain_settings, load_chains_document
from scripts.lib.common.paths import REPO_ROOT, env_paths
from scripts.lib.wg.inventory import generate_wg_inventory
from scripts.lib.wg.validate import assert_chain_isolation

PLAYBOOK_RELPATH = "ansible/roles/wg/playbook.yml"


def _ensure_local_tmp() -> None:
    (REPO_ROOT / "ansible" / ".ansible" / "tmp").mkdir(parents=True, exist_ok=True)


def _assert_wg_body_chain(chain: str) -> None:
    paths = env_paths(chain_settings(chain))
    if not paths.chain_generated.is_file():
        print(f"Missing {paths.chain_generated} — inventory generation failed.", file=sys.stderr)
        sys.exit(1)
    gen = yaml.safe_load(paths.chain_generated.read_text()) or {}
    if gen.get("chain_body_protocol") != "awg":
        print(f"Chain {chain!r} is not an AWG body chain.", file=sys.stderr)
        sys.exit(2)


def _run_playbook(chain: str) -> int:
    _ensure_local_tmp()
    env = os.environ.copy()
    env.setdefault("ANSIBLE_LOCAL_TMP", str(REPO_ROOT / "ansible" / ".ansible" / "tmp"))
    env["PYTHONPATH"] = str(REPO_ROOT)

    paths = env_paths(chain_settings(chain))
    pb = (REPO_ROOT / PLAYBOOK_RELPATH).resolve()
    if not pb.is_file():
        print(f"Playbook not found: {pb}", file=sys.stderr)
        return 1

    extra = {
        "awg_chain_name": chain,
        "awg_repo_root": str(REPO_ROOT),
        "awg_pythonpath": str(REPO_ROOT),
    }
    cmd = [
        "ansible-playbook",
        "-i",
        str(paths.inventory_yml),
        str(pb),
        "-e",
        json.dumps(extra, ensure_ascii=False),
    ]
    return subprocess.call(cmd, env=env)


def deploy_wg_body(chain: str, *, doc: dict[str, Any] | None = None) -> int:
    """Validate cross-chain isolation, generate inventory, run ansible/roles/wg playbook."""
    assert_chain_isolation(doc if doc is not None else load_chains_document())
    generate_wg_inventory(chain)
    _assert_wg_body_chain(chain)
    return _run_playbook(chain)
