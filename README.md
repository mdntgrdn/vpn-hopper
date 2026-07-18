# AWG Ansible controller

**Ansible-based control plane for multi-hop AmneziaWG (AWG) VPN chains.**

Define your hosts and topology once in `chains.yaml`, then deploy a multi-hop
AWG chain (`entry → middle… → exit`) with a single toolchain. Every hop runs an
AmneziaWG server; client traffic enters at the entry node and egresses at the
exit node.

The entry node can optionally be wrapped in a VLESS-over-TLS proxy (Xray) —
either **vless-http** (raw TCP + XTLS Vision) or **vless-grpc** (gRPC transport):
clients connect over TLS/443 and their traffic is forwarded into the local AWG
tunnel. The wrapper is a separate layer deployed last — the AWG body never
references it.

Host keys and the client registry stay on the servers; the controller does not
store secrets in git.

Built for operators who run **self-hosted AmneziaWG** (Docker, policy routing)
with repeatable SSH-driven automation. Each chain uses its **name** as the
deploy prefix (`/opt/vpn-hopper/<chain>/`); several chains can share one VPS as
long as ports and subnets do not overlap.

## Prerequisites

- Python 3.12+, PyYAML, Jinja2, Ansible on the machine that runs playbooks
- SSH access to every chain node (credentials from `chains.yaml`)
- Nodes: automatic Docker install targets Debian; on other OS families install
  the `docker` package yourself or via the role

```bash
pip install -r requirements.txt
# or: poetry install
```

Run all commands below from the **repository root**.

### Repository layout

| Path | What it is |
|------|------------|
| `chains.yaml` | Your hosts and chain definitions (not in git) |
| `ansible/chains/<name>/` | Per-chain working data (`.work/`, inventory; not in git) |
| `ansible/components/awg/` | **Build artifacts**: AWG Dockerfile and WG Jinja templates |
| `ansible/components/vless-http/`, `ansible/components/vless-grpc/` | **Build artifacts**: Xray Dockerfile and wrapper config templates |
| `ansible/roles/wg/` | The AWG body role (`defaults/`, `tasks/`, playbooks) |
| `ansible/roles/vless_http/`, `ansible/roles/vless_grpc/` | The wrapper roles (entry-node Xray) |
| `scripts/` | Controller CLI (`run_ansible.py`, `add_clients.py`, `list_clients.py`, `remove_clients.py`, `destroy_chain.py`) |
| `clients/<chain>/` | Client exports (`.conf`, and `.vless.txt`/`.vless.json` for wrappers) — kept after `.work/` cleanup |

---

## `chains.yaml`

Copy **`chains.yaml.example`** → **`chains.yaml`** (not committed). One file holds
the server catalog and all chains.

### Top level

| Key | Description |
|-----|-------------|
| `hosts` | Machine catalog (SSH, `public_ip`); legacy key `servers` still works |
| `chains` | Named chains |

### `hosts.<name>` — host catalog

| Field | Required | Description |
|-------|----------|-------------|
| `host` | yes | IP or hostname for SSH |
| `user` | yes | SSH user |
| `ssh_private_key_file` | yes | Path to SSH private key |
| `public_ip` | yes | Public IP for client endpoints and tunnels |

### `chains.<name>` — chain settings

A chain is an ordered **`path:`** of AWG hops. Each item is a hop: set `host:`
(from the catalog) and `protocol: awg`. `role` defaults to `server` and the
position (`entry` | `middle` | `exit`) is inferred from path order.

```yaml
chains:
  my-chain:
    awg:
      base_port: 51830
      tunnel_subnet: "10.60.0.0/29"
      routing_table: 200
      wan_iface: eth0
      client_subnet: "10.50.0.0/16"
    path:
      - host: entry
        protocol: awg
      - host: middle
        protocol: awg
      - host: exit
        protocol: awg
```

#### `awg:` block

| Field | Description |
|-------|-------------|
| `base_port` | UDP `ListenPort` of the entry hop; each later hop uses `base_port + index` |
| `tunnel_subnet` | Inter-hop tunnel IPs (one usable host per hop) |
| `routing_table` | Policy-routing table id and fwmark used on the chain |
| `wan_iface` | WAN interface on the **exit** node for NAT/MASQUERADE (e.g. `eth0`, `ens3`) |
| `client_subnet` | Client VPN pool for the whole chain |

VPN clients are **not** in `chains.yaml` — add them with `add_clients.py`; they are
stored in `awg/awg_clients.yml` on the chain entry host.

**Deploy prefix:** `chains.<name>` → `/opt/vpn-hopper/<name>/`; the Docker image
and container use the chain name (must be ≤15 chars for awg-quick).

A hop may also use the explicit list form `segments: [ { protocol: awg } ]`, and
the legacy `servers: [a, b, c]` shorthand is still accepted — but `protocol: awg`
inline is the canonical form. See **`chains.yaml.example`**.

#### `wrapper:` — optional VLESS proxy on the entry hop

The **entry** hop may carry a `wrapper:` block. It deploys a standalone Xray
container on the entry node (VLESS over TLS) that forwards all client traffic
into the local AWG tunnel via the chain `routing_table` fwmark. The AWG body is
deployed exactly the same — the wrapper is an extra layer applied last. One
wrapper per chain; pick `vless-http` (raw TCP + XTLS Vision) or `vless-grpc`
(gRPC transport).

```yaml
    path:
      - host: entry
        wrapper:
          protocol: vless-grpc          # or vless-http
          listen_port: 443
          server_name: vpn.example.com   # required (TLS SNI)
          service_name: grpc            # vless-grpc only (gRPC path; default "grpc")
          # cert_file / key_file         # optional; otherwise Let's Encrypt (certbot)
        protocol: awg
      - host: exit
        protocol: awg
```

| Field | Required | Description |
|-------|----------|-------------|
| `protocol` | yes | `vless-http` or `vless-grpc` |
| `server_name` | yes | TLS SNI / certificate domain (port 80 must be free for certbot) |
| `listen_port` | no | TLS listen port (default `443`) |
| `service_name` | no | gRPC service path (`vless-grpc` only; default `grpc`) |
| `cert_file` / `key_file` | no | Explicit cert; if omitted, a Let's Encrypt cert is issued |

The wrapper deploys automatically at the end of `run_ansible.py`. Clients are
stored in `<protocol>/vless_clients.yml` on the entry host (e.g.
`vless-grpc/vless_clients.yml`) and exported as `clients/<chain>/<name>.vless.txt`
(URI) + `.vless.json` (profile).

---

## Commands

Run from the repository root: `python3 scripts/<script>.py --chain NAME`. Pass
extra Ansible arguments after `--`.

| Script | Purpose |
|--------|---------|
| `run_ansible.py` | Deploy or repair the full AWG chain (plus the wrapper, if defined) |
| `add_clients.py` | Add client(s): `-u "A, B"` (comma-separated; `-u` may repeat). Creates an AWG peer, and a vless-http client too when the chain has a wrapper |
| `list_clients.py` | List clients on the chain entry (AWG, and vless-http if wrapped) |
| `remove_clients.py` | Remove client(s): `-u "A, B"`. Drops the AWG peer (and the vless-http client when the chain has a wrapper) |
| `destroy_chain.py` | Remove container, image and chain data on nodes (incl. the wrapper), plus local workspace (`--yes` to skip the prompt) |

---

## Clients on the server

On each node, data lives under `deploy_dir` (default `/opt/vpn-hopper/<chain>/`):

```
deploy_dir/
  awg/
    Dockerfile
    <chain>.conf        # rendered server config
    keys/               # node private/public key
    peers/              # neighbor public keys
    awg_clients.yml     # client registry (entry node)
    wg_client_keys/     # per-client key material
  vless-http/ | vless-grpc/   # only on the wrapper (entry) node, named by protocol
    Dockerfile
    config.json         # rendered Xray config
    vless_clients.yml   # wrapper client registry
    letsencrypt/        # certbot config dir (when no explicit cert)
```

Add and list clients on the entry node:

```bash
python3 scripts/add_clients.py --chain my-chain -u "Phone, Laptop"
python3 scripts/list_clients.py --chain my-chain
```

Exports are written under `clients/<chain>/`: `Phone.conf` (AWG), and for
wrapped chains also `Phone.vless.txt` (VLESS URI) + `Phone.vless.json` (profile).

### AWG client IP addresses

On `add_clients`, the next free address is taken from `client_subnet` based on
the registry on the entry host. Removed clients free their address for reuse.
The registry is authoritative, not the live WireGuard config file.

---

## Multiple chains on one VPS

Use unique chain names and non-overlapping `awg_base_port`, `client_subnet`, and
`tunnel_subnet` per chain. Containers use host networking — UDP ports and tunnel
IPs must not collide.
