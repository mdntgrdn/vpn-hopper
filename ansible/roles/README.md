# ansible/roles/ — deploy layout

Active deploy logic: playbooks, defaults, tasks per body protocol.

## Layout

```
roles/
  common/      # shared paths, prepare, cleanup
  wg/          # AWG body chain
    playbook.yml
    defaults/
    tasks/
  vless_http/  # vless-http wrapper (raw TCP + XTLS Vision) on the entry host
    playbook.yml
    add_peer.yml
    remove_peer.yml
    fetch_clients.yml
    destroy.yml
    defaults/
    tasks/
  vless_grpc/  # vless-grpc wrapper (gRPC transport) on the entry host
    playbook.yml
    add_peer.yml
    remove_peer.yml
    fetch_clients.yml
    destroy.yml
    defaults/
    tasks/
```

One wrapper per chain; the protocol is chosen by `wrapper.protocol` in
`chains.yaml` and dispatched via `scripts/lib/common/wrappers.py`.

## Deploy a chain

```bash
python3 scripts/run_ansible.py --chain awg-3hop
```

Flow:

```
scripts/run_ansible.py
  → scripts/lib/wg/inventory.py        # writes inventory + chain_generated.yml
  → ansible/roles/wg/playbook.yml       # AWG body
    → roles/wg/tasks/*
    → roles/common/tasks/*
    → scripts/lib/wg/render_configs.py
  → scripts/lib/common/wrappers.py            # dispatch by wrapper.protocol
    → scripts/lib/vless_{http,grpc}/deploy_wrapper.py  # only when chain has a wrapper
      → ansible/roles/vless_{http,grpc}/playbook.yml
```

Shared Python lives in `scripts/lib/` (`common/`, `wg/`, `vless_http/`,
`vless_grpc/`).
