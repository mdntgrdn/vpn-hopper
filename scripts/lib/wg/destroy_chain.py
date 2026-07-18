#!/usr/bin/env python3
"""Tear down a homogeneous AWG (WG) body chain.

On every node: stop/remove the AWG container(s), remove the Docker image
and the deploy directory. On the controller: remove the chain workspace
and exported client configs.
"""
from __future__ import annotations

import shutil
import sys
from typing import Any

from scripts.lib.common.chains import (
    chain_settings,
    load_chain_topology,
    load_chains_document,
)
from scripts.lib.common.paths import cleanup_work_dir, env_paths
from scripts.lib.wg.ansible_run import run_wg_playbook
from scripts.lib.wg.inventory import generate_wg_inventory

DESTROY_PLAYBOOK = "destroy.yml"


def _confirm(chain: str, hosts: list[str], deploy_dir: str) -> bool:
    print(
        f"\nThe following will be removed for chain {chain!r}:\n"
        f"  - AWG Docker container(s) and image on nodes: "
        f"{', '.join(hosts) or '-'}\n"
        f"  - Deploy directory on each node: {deploy_dir}\n"
        f"  - Locally: ansible/chains/{chain}/ and clients/{chain}/\n",
        file=sys.stderr,
    )
    try:
        answer = input("Continue? [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def destroy_wg_body(
    chain: str,
    *,
    assume_yes: bool = False,
    doc: dict[str, Any] | None = None,
) -> int:
    document = doc if doc is not None else load_chains_document()
    topo = load_chain_topology(chain, doc=document)
    settings = chain_settings(chain, doc=document)
    hosts = list(topo.path_hosts)
    deploy_dir = str(settings["deploy_dir"])

    if not assume_yes and not _confirm(chain, hosts, deploy_dir):
        print("Cancelled.", file=sys.stderr)
        return 0

    generate_wg_inventory(chain)
    if topo.has_wrapper:
        from scripts.lib.common.wrappers import run_destroy, wrapper_protocol

        rc = run_destroy(chain, wrapper_protocol(topo), topo.wrapper_host)
        if rc != 0:
            return rc
    rc = run_wg_playbook(DESTROY_PLAYBOOK, chain)
    if rc != 0:
        return rc

    paths = env_paths(settings)
    cleanup_work_dir(paths)
    if paths.clients_out.is_dir():
        shutil.rmtree(paths.clients_out)

    print(
        f"\nChain {chain!r} destroyed on nodes and locally. "
        f"Redeploy: python3 scripts/run_ansible.py --chain {chain}"
    )
    return 0
