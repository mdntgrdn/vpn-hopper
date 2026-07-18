#!/usr/bin/env python3
"""Run an ansible/roles/wg playbook for a chain."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.paths import REPO_ROOT, env_paths

ROLE_PLAYBOOK_DIR = REPO_ROOT / "ansible" / "roles" / "wg"


def _ensure_local_tmp() -> None:
    (REPO_ROOT / "ansible" / ".ansible" / "tmp").mkdir(parents=True, exist_ok=True)


def run_wg_playbook(playbook_name: str, chain: str, *, extra_vars: dict | None = None) -> int:
    paths = env_paths(chain_settings(chain))
    if not paths.inventory_yml.is_file():
        print(f"Missing {paths.inventory_yml} — generate inventory first.", file=sys.stderr)
        return 1
    pb = (ROLE_PLAYBOOK_DIR / playbook_name).resolve()
    if not pb.is_file():
        print(f"Playbook not found: {pb}", file=sys.stderr)
        return 1

    _ensure_local_tmp()
    env = os.environ.copy()
    env.setdefault("ANSIBLE_LOCAL_TMP", str(REPO_ROOT / "ansible" / ".ansible" / "tmp"))
    env["PYTHONPATH"] = str(REPO_ROOT)

    extra = {
        "awg_chain_name": chain,
        "awg_repo_root": str(REPO_ROOT),
        "awg_pythonpath": str(REPO_ROOT),
        **(extra_vars or {}),
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
