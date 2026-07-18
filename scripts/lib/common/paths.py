"""Repository and per-chain workspace paths."""
from __future__ import annotations

import pathlib
import shutil
import sys
from dataclasses import dataclass
from typing import Any

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
ANSIBLE_ROOT = REPO_ROOT / "ansible"
CHAINS_VARS_PATH = REPO_ROOT / "chains.yaml"
CHAINS_VARS_EXAMPLE_PATH = REPO_ROOT / "chains.yaml.example"
ENVS_DIR = ANSIBLE_ROOT / "chains"
DEPLOY_ROOT = "/opt/vpn-hopper"
AWG_QUICK_INTERFACE_MAX_LEN = 15

CHAIN_SETTING_KEYS = (
    "awg_base_port",
    "client_subnet",
    "tunnel_subnet",
    "routing_table",
    "wan_iface",
    "deploy_dir",
    "docker_image_name",
    "docker_container_name",
)

_DERIVED_DEPLOY_KEYS = frozenset(
    {"deploy_dir", "docker_image_name", "docker_container_name", "awg_deploy_conf_basename"}
)

REMOTE_HOST_KEYS_DIR = "keys"
REMOTE_AWG_CLIENTS_BASENAME = "awg_clients.yml"
REMOTE_PEERS_DIR = "peers"

REMOTE_VLESS_HTTP_DIR = "vless-http"
REMOTE_VLESS_CLIENTS_BASENAME = "vless_clients.yml"
VLESS_HTTP_API_PORT_DEFAULT = 10086
VLESS_HTTP_INBOUND_TAG = "vless-in"

REMOTE_VLESS_GRPC_DIR = "vless-grpc"
VLESS_GRPC_API_PORT_DEFAULT = 10086
VLESS_GRPC_INBOUND_TAG = "vless-grpc-in"


@dataclass(frozen=True)
class EnvPaths:
    chain_name: str
    chain_root: pathlib.Path
    work: pathlib.Path
    work_group_vars: pathlib.Path
    artifacts: pathlib.Path
    chain_generated: pathlib.Path
    chain_runtime: pathlib.Path
    awg_clients: pathlib.Path
    vless_clients: pathlib.Path
    awg_configs: pathlib.Path
    vless_http_configs: pathlib.Path
    vless_grpc_configs: pathlib.Path
    inventory_yml: pathlib.Path
    host_vars_dir: pathlib.Path
    clients_out: pathlib.Path


def load_yaml(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text())
    return data if isinstance(data, dict) else {}


def _is_ansible_jinja(value: Any) -> bool:
    return isinstance(value, str) and "{{" in value


def env_paths(settings: dict[str, Any]) -> EnvPaths:
    cname = str(settings["awg_chain_name"])
    root = ENVS_DIR / cname
    work = root / ".work"
    work_gv = work / "group_vars"
    return EnvPaths(
        chain_name=cname,
        chain_root=root,
        work=work,
        work_group_vars=work_gv,
        artifacts=work / "artifacts",
        chain_generated=work_gv / "chain_generated.yml",
        chain_runtime=work_gv / "chain_runtime.yml",
        awg_clients=work_gv / "awg_clients.yml",
        vless_clients=work_gv / "vless_clients.yml",
        awg_configs=work / "configs",
        vless_http_configs=work / "vless_http_configs",
        vless_grpc_configs=work / "vless_grpc_configs",
        inventory_yml=work / "inventory.yml",
        host_vars_dir=work / "host_vars",
        clients_out=REPO_ROOT / "clients" / cname,
    )


def ensure_work_dirs(paths: EnvPaths) -> EnvPaths:
    paths.work.mkdir(parents=True, exist_ok=True)
    paths.artifacts.mkdir(parents=True, exist_ok=True)
    paths.work_group_vars.mkdir(parents=True, exist_ok=True)
    paths.host_vars_dir.mkdir(parents=True, exist_ok=True)
    paths.awg_configs.mkdir(parents=True, exist_ok=True)
    paths.vless_http_configs.mkdir(parents=True, exist_ok=True)
    paths.vless_grpc_configs.mkdir(parents=True, exist_ok=True)
    return paths


def cleanup_work_dir(paths: EnvPaths) -> None:
    if paths.chain_root.is_dir():
        shutil.rmtree(paths.chain_root)


def cleanup_legacy_chain_layout(paths: EnvPaths) -> None:
    legacy_inv = paths.chain_root / "inventory.yml"
    if legacy_inv.is_file():
        legacy_inv.unlink()
    legacy_gv = paths.chain_root / "group_vars"
    if legacy_gv.is_dir():
        shutil.rmtree(legacy_gv)
    legacy_art = paths.chain_root / "artifacts"
    if legacy_art.is_dir():
        shutil.rmtree(legacy_art)


def refresh_chain_workspace(paths: EnvPaths) -> None:
    cleanup_work_dir(paths)
    cleanup_legacy_chain_layout(paths)


def ansible_group_name(settings: dict[str, Any]) -> str:
    return str(settings["awg_chain_name"])


def chain_params_for_generated(settings: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"awg_chain_name": settings["awg_chain_name"]}
    for key in CHAIN_SETTING_KEYS:
        if key in _DERIVED_DEPLOY_KEYS:
            continue
        val = settings.get(key)
        if val is not None and str(val).strip() != "":
            out[key] = val
    return out


def _validate_chain_name_for_awg(chain_name: str) -> None:
    if len(chain_name) > AWG_QUICK_INTERFACE_MAX_LEN:
        print(
            f"chains.yaml → chains.{chain_name}: chain name {chain_name!r} "
            f"is too long for awg-quick ({len(chain_name)} characters, "
            f"maximum {AWG_QUICK_INTERFACE_MAX_LEN}).",
            file=sys.stderr,
        )
        sys.exit(1)


def finalize_settings(raw: dict[str, Any], *, chain_name: str) -> dict[str, Any]:
    out = dict(raw)
    out.pop("awg_quick_interface", None)
    out["awg_deploy_conf_basename"] = f"{chain_name}.conf"

    deploy = out.get("deploy_dir")
    if not deploy or _is_ansible_jinja(deploy):
        out["deploy_dir"] = f"{DEPLOY_ROOT}/{chain_name}"
    container = out.get("docker_container_name")
    if not container or _is_ansible_jinja(container):
        out["docker_container_name"] = chain_name
    image = out.get("docker_image_name")
    if not image or _is_ansible_jinja(image):
        out["docker_image_name"] = chain_name
    if out.get("awg_base_port") is not None and str(out.get("awg_base_port")).strip() != "":
        out["awg_base_port"] = int(out["awg_base_port"])
    if out.get("routing_table") is not None and str(out.get("routing_table")).strip() != "":
        out["routing_table"] = int(out["routing_table"])

    _validate_chain_name_for_awg(chain_name)
    return out


def remote_deploy_paths(deploy_dir: str) -> dict[str, str]:
    base = deploy_dir.rstrip("/")
    awg = f"{base}/awg"
    return {
        "awg_dir": awg,
        "host_keys_dir": f"{awg}/{REMOTE_HOST_KEYS_DIR}",
        "host_private_key": f"{awg}/{REMOTE_HOST_KEYS_DIR}/private.key",
        "host_public_key": f"{awg}/{REMOTE_HOST_KEYS_DIR}/public.key",
        "awg_clients": f"{awg}/{REMOTE_AWG_CLIENTS_BASENAME}",
        "peers_dir": f"{awg}/{REMOTE_PEERS_DIR}",
    }


def peer_public_key_remote_path(deploy_dir: str, peer_hostname: str) -> str:
    return f"{deploy_dir.rstrip('/')}/awg/{REMOTE_PEERS_DIR}/{peer_hostname}_public.key"


def remote_vless_http_paths(deploy_dir: str) -> dict[str, str]:
    """On-node layout for the vless-http wrapper under the chain deploy_dir."""
    base = deploy_dir.rstrip("/")
    vh = f"{base}/{REMOTE_VLESS_HTTP_DIR}"
    return {
        "vless_http_dir": vh,
        "config_json": f"{vh}/config.json",
        "vless_clients": f"{vh}/{REMOTE_VLESS_CLIENTS_BASENAME}",
        "letsencrypt_dir": f"{vh}/letsencrypt",
        "dockerfile": f"{vh}/Dockerfile",
    }


def remote_vless_grpc_paths(deploy_dir: str) -> dict[str, str]:
    """On-node layout for the vless-grpc wrapper under the chain deploy_dir."""
    base = deploy_dir.rstrip("/")
    vg = f"{base}/{REMOTE_VLESS_GRPC_DIR}"
    return {
        "vless_grpc_dir": vg,
        "config_json": f"{vg}/config.json",
        "vless_clients": f"{vg}/{REMOTE_VLESS_CLIENTS_BASENAME}",
        "letsencrypt_dir": f"{vg}/letsencrypt",
        "dockerfile": f"{vg}/Dockerfile",
    }
