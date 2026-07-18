"""chains.yaml loading and chain settings."""
from __future__ import annotations

import sys
from typing import Any

import yaml

from scripts.lib.common.paths import (
    CHAINS_VARS_EXAMPLE_PATH,
    CHAINS_VARS_PATH,
    CHAIN_SETTING_KEYS,
    EnvPaths,
    chain_params_for_generated,
    env_paths,
    finalize_settings,
    load_yaml,
)
from scripts.lib.common.topology import build_chain_topology, extract_deploy_settings

__all__ = [
    "chain_params_for_generated",
    "ensure_chains_file",
    "load_chain_entry",
    "load_chain_settings",
    "load_chain_topology",
    "load_chains_document",
    "chain_settings",
]


def ensure_chains_file():
    if CHAINS_VARS_PATH.is_file():
        return CHAINS_VARS_PATH
    if CHAINS_VARS_EXAMPLE_PATH.is_file():
        print(
            f"Create {CHAINS_VARS_PATH} (copy from {CHAINS_VARS_EXAMPLE_PATH.name}).",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Missing {CHAINS_VARS_PATH}.", file=sys.stderr)
    sys.exit(1)


def load_chains_document() -> dict[str, Any]:
    return load_yaml(ensure_chains_file())


def load_chain_entry(chain_name: str, *, doc: dict[str, Any] | None = None) -> dict[str, Any]:
    name = chain_name.strip()
    if not name:
        print("chain_name must not be empty.", file=sys.stderr)
        sys.exit(2)
    document = doc or load_chains_document()
    chains = document.get("chains")
    if not isinstance(chains, dict):
        print("chains.yaml requires a chains key (dict).", file=sys.stderr)
        sys.exit(1)
    entry = chains.get(name)
    if not isinstance(entry, dict):
        known = ", ".join(sorted(str(k) for k in chains)) or "(empty)"
        print(f"Chain {name!r} not found in chains.yaml. Available: {known}.", file=sys.stderr)
        sys.exit(1)
    return entry


def _chain_params_from_entry(entry: dict[str, Any], chain_name: str, *, topo) -> dict[str, Any]:
    if "defaults" in entry:
        print(
            f"chains.yaml → chains.{chain_name} must not have a defaults key; "
            "set parameters under awg: or at chain level.",
            file=sys.stderr,
        )
        sys.exit(1)
    raw = extract_deploy_settings(entry, chain_name)
    if topo.client_subnet:
        raw["client_subnet"] = topo.client_subnet
    raw["chain_is_awg"] = topo.is_awg_chain
    return raw


def _require_awg_params(raw: dict[str, Any], chain_name: str) -> None:
    missing = [
        k
        for k in CHAIN_SETTING_KEYS
        if k not in ("deploy_dir", "docker_image_name", "docker_container_name")
        and (raw.get(k) is None or str(raw.get(k)).strip() == "")
    ]
    if missing:
        print(
            f"chains.yaml → chains.{chain_name}: set chain parameters: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)


def chain_settings(chain_name: str, *, doc: dict[str, Any] | None = None) -> dict[str, Any]:
    document = doc or load_chains_document()
    if document.get("defaults") is not None:
        print("chains.yaml: defaults key is deprecated.", file=sys.stderr)
        sys.exit(1)
    entry = load_chain_entry(chain_name, doc=document)
    topo = build_chain_topology(chain_name=chain_name, entry=entry, doc=document)
    raw = _chain_params_from_entry(entry, chain_name, topo=topo)
    if topo.is_awg_chain:
        _require_awg_params(raw, chain_name)
    settings = finalize_settings(raw, chain_name=chain_name)
    settings["awg_chain_name"] = chain_name
    return settings


def load_chain_topology(chain_name: str, *, doc: dict[str, Any] | None = None):
    document = doc or load_chains_document()
    entry = load_chain_entry(chain_name, doc=document)
    return build_chain_topology(chain_name=chain_name, entry=entry, doc=document)


def load_chain_settings(*, chain_name: str) -> dict[str, Any]:
    base = chain_settings(chain_name)
    paths = env_paths(base)
    gen = load_yaml(paths.chain_generated)
    for key in CHAIN_SETTING_KEYS:
        if key in gen and gen[key] is not None:
            base[key] = gen[key]
    if gen.get("awg_chain_name"):
        base["awg_chain_name"] = gen["awg_chain_name"]
    return finalize_settings(base, chain_name=str(base["awg_chain_name"]))
