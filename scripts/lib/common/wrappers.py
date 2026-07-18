#!/usr/bin/env python3
"""Dispatch wrapper operations to the per-protocol implementation.

Each wrapper protocol (vless-http, vless-grpc) has its own Ansible role and
``scripts/lib/<pkg>`` package exposing the same surface: ``deploy_wrapper``,
``add_clients``, ``remove_clients``, ``fetch_clients.list_clients`` and an
``ansible_run`` playbook runner. This module routes by ``wrapper.protocol``.
"""
from __future__ import annotations

from importlib import import_module

from scripts.lib.common.topology import (
    PROTO_VLESS_GRPC,
    PROTO_VLESS_HTTP,
    ChainTopology,
)

_WRAPPER_PACKAGES = {
    PROTO_VLESS_HTTP: "scripts.lib.vless_http",
    PROTO_VLESS_GRPC: "scripts.lib.vless_grpc",
}
_PLAYBOOK_RUNNERS = {
    PROTO_VLESS_HTTP: "run_vless_http_playbook",
    PROTO_VLESS_GRPC: "run_vless_grpc_playbook",
}


def wrapper_protocol(topo: ChainTopology) -> str:
    cfg = topo.wrapper_config() or {}
    return str(cfg.get("protocol") or "").strip()


def _module(protocol: str, submodule: str):
    pkg = _WRAPPER_PACKAGES.get(protocol)
    if not pkg:
        raise SystemExit(f"Unknown wrapper protocol {protocol!r}.")
    return import_module(f"{pkg}.{submodule}")


def deploy_wrapper(chain: str, protocol: str, *, generate: bool = True) -> int:
    mod = _module(protocol, "deploy_wrapper")
    return mod.deploy_wrapper(chain, generate=generate)


def add_clients(
    chain: str, names: list[str], protocol: str, *, generate: bool = True
) -> int:
    mod = _module(protocol, "add_clients")
    return mod.add_clients(chain, names, generate=generate)


def remove_clients(
    chain: str, names: list[str], protocol: str, *, generate: bool = True
) -> int:
    mod = _module(protocol, "remove_clients")
    return mod.remove_clients(chain, names, generate=generate)


def list_clients(
    chain: str, protocol: str, *, fmt: str = "table", generate: bool = True
) -> int:
    mod = _module(protocol, "fetch_clients")
    return mod.list_clients(chain, fmt=fmt, generate=generate)


def export_clients(
    chain: str, names: list[str], protocol: str, *, generate: bool = True
) -> int:
    mod = _module(protocol, "export_clients")
    return mod.export_clients(chain, names, generate=generate)


def run_destroy(chain: str, protocol: str, host: str) -> int:
    mod = _module(protocol, "ansible_run")
    runner = getattr(mod, _PLAYBOOK_RUNNERS[protocol])
    return runner("destroy.yml", chain, extra_vars={"vless_wrapper_host": host})
