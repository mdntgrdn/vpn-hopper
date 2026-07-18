#!/usr/bin/env python3
"""Deploy the vless-http wrapper on the chain entry host (runs last, separately).

The AWG body playbook never references the wrapper; this is a standalone layer
invoked after the chain is up (auto from run_ansible.py, or manually).
"""
from __future__ import annotations

import sys

from scripts.lib.common.chains import chain_settings
from scripts.lib.common.paths import env_paths, load_yaml
from scripts.lib.vless_http.ansible_run import run_vless_http_playbook
from scripts.lib.wg.inventory import generate_wg_inventory

DEPLOY_PLAYBOOK = "playbook.yml"


def has_wrapper(chain: str) -> bool:
    paths = env_paths(chain_settings(chain))
    gen = load_yaml(paths.chain_generated)
    return bool(gen.get("chain_has_wrapper"))


def deploy_wrapper(chain: str, *, generate: bool = True) -> int:
    if generate:
        generate_wg_inventory(chain)
    if not has_wrapper(chain):
        print(f"chains.{chain}: no wrapper defined — nothing to deploy.", file=sys.stderr)
        return 0
    paths = env_paths(chain_settings(chain))
    host = str(load_yaml(paths.chain_generated).get("chain_wrapper_host") or "")
    rc = run_vless_http_playbook(
        DEPLOY_PLAYBOOK, chain, extra_vars={"vless_wrapper_host": host}
    )
    if rc == 0:
        print(f"vless-http wrapper deployed on {host!r}.")
    return rc


def main(argv: list[str] | None = None) -> int:
    import argparse

    from scripts.lib.common.cli import add_chain_cli

    ap = argparse.ArgumentParser(description="Deploy the vless-http wrapper for a chain")
    add_chain_cli(ap)
    args = ap.parse_args(argv)
    return deploy_wrapper(args.chain)


if __name__ == "__main__":
    raise SystemExit(main())
