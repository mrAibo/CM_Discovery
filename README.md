# IBM Patchwatch — portable update table

The simplest workflow is one HTML file on Windows plus the existing offline
collector. Open `docs/IBM-Patchwatch.html` in your browser, then select the
collector's `inventory.json`. The embedded catalog is visible even without an
inventory file. No Windows installation, local web server, extension, or SSH
connection from Windows is required.

## Recommended: portable page

1. Download `docs/IBM-Patchwatch.html` with GitHub's **Download raw file** button
   and open it in a current Windows browser.
2. Run the existing collector on the CM server:

   ```bash
   python3 collectors/ibm_discovery.py --json > inventory.json
   ```

3. Transfer that JSON file using an approved existing LAN/file-transfer method
   and click **Открыть inventory.json** in the page.
4. Open the IBM download or Fix Central links in the row. Some links go directly
   to a fix selection; others require product/platform selection on IBM's page.
   IBMid, entitlement checks, license acceptance, and actual downloads remain on IBM.

The HTML contains inline CSS, JavaScript, and the catalog, with no external
dependencies. The page makes **no network requests** and reads files only when
selected. Its CSP disables network connections. Inventory stays in browser memory
and is discarded when the page closes; opening an IBM link does not upload it.

### Rebuilding and refreshing

```bash
python3 scripts/build_static_page.py
```

The builder is Python 3.6+ standard library and does not need the central
application installed. GitHub Actions rebuilds the public, inventory-free HTML
after each successful catalog refresh and commits it alongside `catalog.json`.
Download a fresh HTML periodically, or import a newer `catalog.json` with the
control under **Как пользоваться и обновлять таблицу**. Opening an old HTML does
not refresh it automatically.

For an explicitly private report with inventory embedded:

```bash
python3 scripts/build_static_page.py --inventory /private/inventory.json --output /private/IBM-Patchwatch-report.html
```

Do not commit private reports. The builder refuses to embed inventory into the
tracked public HTML path.

### What the comparison proves

- Versions compare only inside the displayed product stream. A different stream
  requires review; major-version changes are not inferred.
- Unknown or conflicting iFix/build values, discovery errors, stale/undated
  catalog entries, and failed source refreshes cannot produce a matching status.
- CM and WAS base/fix-pack matches do not certify interim/security-fix coverage.
- Db2 special-build numbers do not imply chronology. Unequal builds require review.
- Daeja detected in ICN's `version.txt` is a bundled component. ICN 3.1 IF12's
  Readme includes Daeja 26.0.0 iFix 1; standalone 5.0.15 iFix6 is not an automatic
  recommendation for that bundled installation.
- ICCSAP IM `JRE_fix_YYYYMMDD` dates are displayed as evidence, not converted into
  measured Java versions. Its embedded JRE is distinct from WebSphere's SDK.

`web/verified-notes.json` contains dated IBM observations, conditions and download
links. Version-specific notes disappear when the imported catalog's target changes.
The catalog timestamp and this file's review date remain separate.

**Known source limitation:** some existing providers read a pinned readme for a
known release. Successfully fetching that page again does not discover the next
release or prove that the target is the latest. The static UI calls these
confirmed levels, exposes dates, and flags source age. Better product-index
discovery can be added to the catalog independently of the browser workflow.

## Optional: existing central LAN checker

A short-lived LAN web application that discovers installed IBM Content Manager components over SSH and compares them with a catalog maintained from official IBM sources.

Nothing is installed on the Windows workstation. The browser receives inventory from the central Linux server and reads the public update catalog from GitHub. IBM credentials remain on IBM websites.

## Architecture

```text
IBM CM server                 Central Linux server                Windows browser
/root/bin/ibm_discovery.py <- restricted SSH -- ibm-patchwatch serve -> LAN HTTP
                                                                    |
                                           GitHub catalog.json <----+
```

- The IBM CM server does not need internet access.
- Inventory stays inside the LAN and is never uploaded to GitHub.
- GitHub Actions refreshes `data/ibm/catalog.json` daily from official IBM pages.
- Version comparison is conservative: missing, stale or ambiguous data becomes `CHECK_REQUIRED` rather than a false `CURRENT`.

## Requirements

### IBM CM server

- Linux
- Python 3.6 or newer
- Commands required by the detected IBM products (`cmlevel`, `db2level`, WebSphere `versionInfo`, and related local files)
- root execution, because the collector must inspect all configured installations

### Central Linux server

- Linux with access to the IBM CM server over SSH
- internet access to GitHub
- Python 3.11 or newer
- Git and OpenSSH client

### Windows workstation

- A current browser
- LAN access to the central Linux server
- internet access to `raw.githubusercontent.com` and IBM support pages

## Installation

### 1. Install the collector on the IBM CM server

Clone this repository on the central Linux server, then copy the single dependency-free collector to the CM server:

```bash
git clone https://github.com/mrAibo/CM_Discovery.git
cd CM_Discovery
ssh root@cmserver 'mkdir -p /root/bin && chmod 700 /root/bin'
scp collectors/ibm_discovery.py root@cmserver:/root/bin/
ssh root@cmserver 'chmod 700 /root/bin/ibm_discovery.py'
```

Verify it locally on the CM server:

```bash
/root/bin/ibm_discovery.py --json | python3 -m json.tool >/dev/null
```

Expected result: exit code `0` and no JSON error.

### 2. Create a restricted SSH key

On the central Linux server:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_cm_discovery -C ibm-cm-discovery
```

Add the generated public key to `/root/.ssh/authorized_keys` on the CM server. Restrict it to the central server's LAN address and the collector command:

```text
from="<CENTRAL_LINUX_LAN_IP>",restrict,command="/usr/bin/python3 /root/bin/ibm_discovery.py --json" ssh-ed25519 AAAA...
```

Add an alias on the central server in `~/.ssh/config`:

```sshconfig
Host cmtest
    HostName <IBM_CM_LAN_IP_OR_NAME>
    User root
    IdentityFile ~/.ssh/id_cm_discovery
    IdentitiesOnly yes
```

Test the forced command:

```bash
ssh -T cmtest | python3 -m json.tool >/dev/null
```

The restricted key cannot open a shell or forward ports; it can only run discovery.

### 3. Install the central application

From the repository checkout on the central Linux server:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
cp config.example.toml config.toml
```

`config.toml`:

```toml
[ssh]
command = "ssh"
connect_timeout = 15
collector_timeout = 60

[hosts.cmtest]
collector = "/root/bin/ibm_discovery.py"
```

`config.toml` is ignored by Git.

### 4. Start the temporary checker

```bash
. .venv/bin/activate
IBM_CHECK_USER=admin \
IBM_CHECK_PASSWORD=admin \
ibm-patchwatch --config config.toml serve cmtest \
  --bind <CENTRAL_LINUX_LAN_IP> \
  --port 8765
```

Open from Windows:

```text
http://<CENTRAL_LINUX_LAN_IP>:8765/
```

The browser asks for the configured username and password. Stop the server with `Ctrl+C` when the check is finished.

`admin/admin` is the requested default and only prevents casual access. HTTP Basic Auth is not encryption; use this mode only for the confirmed trusted LAN. Set different environment values or place the application behind an existing HTTPS reverse proxy if the network boundary expands.

## Result statuses

- `CURRENT` — installed maintenance level matches the catalog.
- `UPDATE_AVAILABLE` — a newer applicable level is known.
- `NEWER_THAN_CATALOG` — installed level is newer than the catalog.
- `CHECK_REQUIRED` — data is missing, stale or unsafe to compare automatically.
- `NOT_SUPPORTED` — the catalog explicitly marks the product stream unsupported.

DB2 special builds are not treated as ordinary numeric versions. A non-identical special build at the same DB2 version requires review.

## Updating

On the central Linux server:

```bash
cd CM_Discovery
git pull --ff-only
. .venv/bin/activate
python -m pip install -e .
```

When the collector changes, copy it to the CM server again and repeat the JSON verification from step 1.

## Development checks

```bash
python -m pip install pytest
python -m pytest -q
```

The repository intentionally keeps two runtime closures:

- `collectors/ibm_discovery.py` — offline CM inventory collector;
- `src/ibm_patchwatch/` plus `scripts/update_ibm_catalog.py` — central web checker and GitHub catalog refresh.

## Security boundaries

- Do not place SSH private keys, `config.toml`, IBM credentials or inventory snapshots in Git.
- Bind the web server to a private LAN address, not a public interface.
- IBM download links open directly in the Windows browser; the application never receives IBMid credentials.
- Malformed SSH output prevents the web server from starting.

## Limitations

- Physical SSH and IBM product discovery must be verified in the target environment.
- IBM entitlement, license acceptance and downloads remain manual in IBM Fix Central.
- The application does not install patches or infer interim-fix supersedence unless the catalog explicitly establishes it.
