# Remote LAN Update Checker v0.1

## Goal

Run IBM discovery on a Content Manager host over restricted root SSH, then expose the fresh inventory and an update-comparison browser UI temporarily from an internet-enabled Linux server on the same LAN as the Windows workstation.

## Decisions

- The collector remains at `/root/bin/ibm_discovery.py` on the Content Manager host.
- The central CLI uses the existing SSH host alias and collector configuration.
- Discovery runs once before the web server starts; restarting the on-demand server creates a fresh snapshot.
- The server uses Python stdlib `ThreadingHTTPServer` and binds to an explicitly selected LAN address.
- Every local route uses HTTP Basic Auth. Defaults are `admin/admin`; environment variables `IBM_CHECK_USER` and `IBM_CHECK_PASSWORD` override them. HTTP on a trusted LAN is a deliberate low-security boundary.
- Inventory remains in memory/on the central host and is never sent to GitHub.
- The browser loads the public catalog from `https://raw.githubusercontent.com/mrAibo/CM_Discovery/main/data/ibm/catalog.json`.
- Comparison is fail-closed: ambiguous, missing, stale, unsupported, or incomparable data never becomes `CURRENT`.
- UI statuses are `CURRENT`, `UPDATE_AVAILABLE`, `NEWER_THAN_CATALOG`, `CHECK_REQUIRED`, and `NOT_SUPPORTED`.
- DB2 special builds are handled conservatively rather than ranked as ordinary numeric versions.
- IBM credentials and automated patch downloads are out of scope.

## Data flow

1. `ibm-patchwatch serve <host>` loads `config.toml`.
2. Existing SSH discovery executes `/root/bin/ibm_discovery.py --json` remotely.
3. Existing inventory validation rejects malformed or incomplete output.
4. The authenticated temporary server exposes the UI and in-memory inventory.
5. Browser JavaScript downloads the public GitHub catalog and compares structured maintenance fields.
6. IBM source/download links open directly in separate browser tabs.
7. The operator stops the process with `Ctrl+C`.

## Security

Use a dedicated SSH key constrained in root's `authorized_keys` by source IP, `restrict`, and a forced collector command. Basic Auth protects against casual LAN access but is not encryption; add TLS/reverse proxy only if the trust boundary expands.

## Verification

- Unit tests for authentication failure/success and all served routes.
- Unit tests for fail-closed comparison statuses, including DB2 ambiguity.
- Full pytest suite.
- Local HTTP acceptance using a synthetic inventory and catalog fixture.
- PR CI must pass before squash merge to `main`.
