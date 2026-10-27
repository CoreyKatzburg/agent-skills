---
name: windows-desktop-ssh
description: Use when a user asks a managed cloud agent to SSH into Corey's Windows desktop through its configured Tailscale network.
---

# SSH to Corey's Windows desktop

Use this skill only for a user-requested, task-scoped connection. It documents how to reach the PC; it does not authorize unrelated inspection or changes.

## Target and account

- Tailnet device: `desktop-ghi2ov5`
- Tailnet IPv4: `100.107.174.14`
- SSH port: `22`
- Windows username: `Corey`
- Windows OpenSSH Server was confirmed running and listening on port 22 on 2026-10-27. Recheck if a later connection fails.
- Corey is in the Windows Administrators group. The authorized public key was added to `C:\ProgramData\ssh\administrators_authorized_keys`; that file is shared by administrator accounts and has ACLs restricted to Administrators and SYSTEM.

The currently authorized public key is:

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN6Bhvhv9M+yIDwEggXsx4brR44EQ6ZYf/GYfUgEFZiw codex-one-time-desktop-access
```

The matching private key is **not included in this skill**. In the current executor it was at `/tmp/codex_desktop_access_ed25519`, which may be temporary and unavailable to other agents. Before connecting, locate a matching private key supplied through an approved secret mount and verify it is readable. If no matching private key is available, do not ask the user to paste a private key or password into chat. Ask them to provision the key securely or authorize a new agent key by adding its public half to the Windows file above.

## Network path from a managed cloud environment

Read and follow the `cloud-environment-runtime` skill's networking and Tailscale VPN instructions before network work.

1. Check the current environment status and `/etc/codex/network-policy.json`. Proceed only when Tailscale access is configured and the TCP policy permits `100.107.174.14` (or the user's current desktop IP) on the authorized path. These values can change.
2. The cloud environment uses a Tailscale sidecar and TCP CONNECT proxy. It does not expose a local Tailscale daemon or interface. Do not install/reconfigure Tailscale, run `tailscale up`, or rely on `tailscale ip -4`; that CLI cannot query the sidecar.
3. Use the `socat` installer and forwarding workflow from `cloud-environment-runtime`'s Tailscale VPN guide. Set `RUNTIME_SKILL_DIR` as that guide describes and capture the installer's printed path in `SOCAT`. Keep the forward running while SSH is connected:

```sh
"$SOCAT" -d -d TCP4-LISTEN:15432,bind=127.0.0.1,reuseaddr,fork \
  PROXY:proxy:100.107.174.14:22,proxyport=8088,resolve=0
```

Choose another free unprivileged loopback port if `15432` is occupied, then use that same port in `ssh`. Stop the forward with Ctrl-C after the connection.

## Connect

Set `DESKTOP_SSH_KEY` to the path of the provisioned private key, then run a bounded, noninteractive command first:

```sh
ssh -p 15432 -i "$DESKTOP_SSH_KEY" \
  -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 \
  -o StrictHostKeyChecking=accept-new \
  Corey@127.0.0.1 whoami
```

Expected output is `desktop-ghi2ov5\corey`. `accept-new` stores a first-seen host key; never disable host-key checking. For stronger first-use verification, compare the SSH host-key fingerprint with the one on the Windows PC before accepting it. Once authenticated, run only commands needed for the user's current request.

## Diagnose failures

- `Permission denied (publickey,...)`: the TCP route and SSH server were reached, but the key was not accepted. Check that the private key matches the public key above, the login name is `Corey`, and the key is present in `C:\ProgramData\ssh\administrators_authorized_keys` with the required ACLs.
- `Connection refused` or timeout: check the desktop's current Tailscale IP, `sshd` service/listener, Windows Firewall, current cloud VPN status, and TCP grant. A local `tailscale` CLI is not a fix for a sidecar routing problem.
- Proxy 403/503 or VPN errors: use the cloud-environment skill's policy and proxy diagnostics; do not bypass its proxy or change routes.
