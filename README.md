# CM Discovery / IBM Patchwatch

Central IBM product discovery and patch intelligence for IBM Content Manager environments.

## Architecture

The project has three layers:

1. `collectors/ibm_discovery.py` runs read-only on an IBM/CM server and emits inventory JSON.
2. `ibm-patchwatch` runs on a central Linux host, calls collectors over SSH, stores snapshots in SQLite, and compares installed maintenance levels with IBM metadata.
3. GitHub Actions refresh `data/ibm/catalog.json` from official IBM sources. The central server can use that GitHub-hosted catalog when direct IBM access is blocked by a corporate proxy.

### Discovered products

The collector currently detects:

- IBM Content Manager (`cmlevel -l`)
- WebSphere Application Server (`versionInfo.sh`)
- IBM SDK Java (`versionInfo.sh`)
- DB2 (`db2level`, with `db2profile` fallback for non-interactive SSH)
- IBM Content Navigator (`ECMClient/version.txt`)
- FileNet CE/PE clients
- Content Manager APIs
- Daeja ViewONE Virtual and iFix level
- IBM Content Collector for SAP Applications
- IBM Installation Manager package information

## Requirements

Central host:

- Linux
- Python 3.11+ (tested target: Python 3.12)
- OpenSSH client
- Git
- SSH access to target IBM servers
- `rich` for the optional GitHub update table

Remote collector:

- Python 3.6+
- no third-party Python dependencies

## SSH configuration

Keep connection details in `~/.ssh/config`:

```sshconfig
Host cmtest
    HostName cm_host123
    User root
    IdentityFile ~/.ssh/id_ed25519
```

Patchwatch only refers to `cmtest`.

## Configuration

```bash
cp config.example.toml config.toml
```

Example:

```toml
[storage]
database = "data/patchwatch.db"

[ssh]
command = "ssh"
connect_timeout = 15
collector_timeout = 60

[hosts.cmtest]
collector = "/root/bin/ibm_discovery.py"
environment = "test"
```

`config.toml` is intentionally ignored by Git.

## Install / update central CLI

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

For an existing checkout use:

```bash
git pull
source scripts/update_env.sh
```

## Patchwatch usage

Scan one host:

```bash
ibm-patchwatch scan cmtest
```

Detailed scan:

```bash
ibm-patchwatch scan cmtest --details
```

Compare installed levels with IBM maintenance metadata:

```bash
ibm-patchwatch check cmtest
```

Show latest stored inventory:

```bash
ibm-patchwatch inventory --details
```

Machine-readable output:

```bash
ibm-patchwatch check cmtest --json --pretty
```

## Rich update table from GitHub

The table implementation deliberately separates data access, comparison, and presentation:

- `src/ibm_patchwatch/github_catalog.py` — Git/GitHub fetch and catalog normalization only.
- `src/ibm_patchwatch/update_report.py` — installed inventory versus GitHub catalog comparison.
- `src/ibm_patchwatch/rich_updates.py` — Rich rendering only.
- `scripts/github_update_table.py` — manual / polling trigger CLI.

The Git source refreshes `origin/main` and reads `data/ibm/catalog.json` directly from the remote-tracking Git ref. It does **not** reset or modify the working tree.

### Global catalog view

This only shows what IBM Patchwatch currently knows as the latest target levels. It does **not** say whether a particular server needs them:

```bash
python scripts/github_update_table.py show
```

### Installed-vs-target host view

This performs a fresh SSH discovery of the configured host and joins it with the latest GitHub catalog. This is the normal update report:

```bash
python scripts/github_update_table.py show --host cmtest
```

The table contains `CURRENT`, `UPDATE`, or `REVIEW` plus the installed and target maintenance levels.

Interactive polling with a fresh host scan every 60 seconds:

```bash
python scripts/github_update_table.py watch --host cmtest --interval 60
```

The table displays a clickable `download` link only when the catalog contains an explicitly verified package/Fix Central URL. Otherwise it displays the IBM `details` / readme link. Patchwatch never fabricates package URLs.

### GitHub-side triggers

`.github/workflows/update-ibm-catalog.yml` refreshes the catalog on:

- manual `workflow_dispatch`
- scheduled daily refresh
- relevant pushes to provider/catalog logic
- GitHub release `published` / `edited` events
- explicit `repository_dispatch` event `refresh-ibm-catalog`

Catalog refresh runs are serialized to avoid concurrent pushes. Provider/network failures are isolated: if one IBM endpoint times out, its last known good entry is preserved and marked with `refresh_error`; the other products can still refresh.

### Server-side scheduled trigger with systemd

The repository contains a user service and timer:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/ibm-patchwatch-updates.service ~/.config/systemd/user/
cp systemd/ibm-patchwatch-updates.timer ~/.config/systemd/user/
```

Create the environment file. `PATCHWATCH_HOST` turns the timer from a catalog-only display into the useful installed-vs-target report:

```bash
mkdir -p ~/.config/ibm-patchwatch
cat > ~/.config/ibm-patchwatch/proxy.env <<'EOF'
PATCHWATCH_HOST=cmtest
PATCHWATCH_CONFIG=/home/xout-adm/bin/CM_Discovery/config.toml
HTTP_PROXY=http://proxy.kkk:8080
HTTPS_PROXY=http://proxy.kkk:8080
http_proxy=http://proxy.kkk:8080
https_proxy=http://proxy.kkk:8080
EOF
chmod 600 ~/.config/ibm-patchwatch/proxy.env
```

Enable the 15-minute refresh timer:

```bash
systemctl --user daemon-reload
systemctl --user enable --now ibm-patchwatch-updates.timer
```

Manual server-side trigger of the same service:

```bash
systemctl --user start ibm-patchwatch-updates.service
```

Show the rendered table from the journal:

```bash
journalctl --user -u ibm-patchwatch-updates.service -n 100 --no-pager
```

Check the timer:

```bash
systemctl --user list-timers ibm-patchwatch-updates.timer
```

The supplied unit assumes the checkout is at `%h/bin/CM_Discovery`. Adjust `WorkingDirectory` and `ExecStart` if the repository lives elsewhere.

## Remote collector test

```bash
ssh cmtest '/root/bin/ibm_discovery.py --json'
```

The one-line JSON form is intentional and ideal for machine transport. Use `--pretty` only for manual debugging.

## Temporary LAN update checker

Run discovery once and expose the in-memory inventory plus a dependency-free browser UI:

```bash
./ibm_discovery.py --serve --bind 0.0.0.0 --port 8765
```

Open `http://CM_HOST:8765/` from the Windows workstation and stop the server with `Ctrl+C` after the check. The Content Manager host makes no outbound requests. IBM pages open in separate tabs; enter the confirmed target level manually because browser same-origin policy prevents the LAN page from reading those tabs. IBMid credentials and cookies remain on IBM's site.

The default bind address is `127.0.0.1`; exposing the checker to the LAN is an explicit `--bind 0.0.0.0` choice. Use it only on a trusted network because the inventory endpoint contains host and installed-product information.

## Proxy

Online IBM providers honor the central host's standard proxy environment. For a classic HTTP CONNECT corporate proxy both variables normally use an `http://` proxy URL, for example:

```bash
export HTTP_PROXY=http://proxy.kkk:8080
export HTTPS_PROXY=http://proxy.kkk:8080
```

No proxy credentials or SSH keys belong in this repository.

## Current maintenance intelligence

Patchwatch currently evaluates the maintenance streams for:

- IBM Content Manager 8.7 fix packs
- IBM Content Navigator 3.1 interim fixes
- IBM Daeja ViewONE 5.0.15 iFixes
- DB2 11.5.9 published cumulative updates
- IBM Java 8 service refresh / fix packs
- ICCSAP 4.0.0.4 embedded-JRE security maintenance
- WebSphere 9.0.5 fix packs

Interim-fix, prerequisite, corequisite and supersedence semantics remain conservative: Patchwatch does not assume cumulative behavior unless IBM explicitly establishes it.
