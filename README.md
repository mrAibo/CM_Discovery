# CM Discovery / IBM Patchwatch

Central IBM product discovery and patch intelligence for IBM Content Manager environments.

## Current scope

The project has two layers:

1. `collectors/ibm_discovery.py` runs read-only on an IBM/CM server and emits inventory JSON.
2. `ibm-patchwatch` runs on a central Linux host, calls collectors over SSH, stores snapshots in SQLite, and will later compare installed levels with IBM online fix sources.

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
- SSH access to target IBM servers

Remote collector:

- Python 3.6+
- no third-party Python dependencies

## SSH configuration

Keep connection details in `~/.ssh/config`:

```sshconfig
Host cmtest
    HostName VNLDICM-D2013
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

## Install central CLI

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## Usage

Scan one host:

```bash
ibm-patchwatch scan cmtest
```

Scan all configured hosts:

```bash
ibm-patchwatch scan all
```

Show latest stored inventory:

```bash
ibm-patchwatch inventory
```

Machine-readable output:

```bash
ibm-patchwatch scan cmtest --json --pretty
ibm-patchwatch inventory --json --pretty
```

## Remote collector test

```bash
ssh cmtest '/root/bin/ibm_discovery.py --json'
```

The one-line JSON form is intentional and ideal for machine transport. Use `--pretty` only for manual debugging.

## Proxy

Online IBM providers will honor the central host's standard proxy environment, e.g. `HTTPS_PROXY`. No proxy credentials or SSH keys belong in this repository.

## Roadmap

1. Remote discovery and inventory snapshots — in progress
2. Normalize Installation Manager package data
3. Cross-validate WAS/Java/ICCSAP versions between product tools and IM
4. IBM WebSphere/Java online provider
5. Content Manager / Content Navigator / ICCSAP / DB2 providers
6. Installed-vs-latest report with supersedence and compatibility awareness
7. Optional download/cache and notifications
