# Project Log

## 2026-09-04 — Remote LAN update checker v0.1

- **Task:** Move the temporary update-check UI to the internet-enabled central Linux server, using fresh remote SSH discovery from the IBM Content Manager host.
- **Decisions:** Collector remains `/root/bin/ibm_discovery.py`; central `ibm-patchwatch serve` owns SSH and LAN HTTP; Basic Auth defaults to `admin/admin` with environment overrides; browser reads the public GitHub catalog directly; inventory never leaves the LAN; comparisons fail closed; DB2 special builds are not numerically ranked.
- **Files changed:** `src/ibm_patchwatch/web.py`, `src/ibm_patchwatch/cli.py`, `tests/test_web.py`, `README.md`, `docs/plans/2026-09-04-remote-lan-update-checker-design.md`.
- **Tests run:** focused pytest, full pytest, Python compileall, git diff check, Node comparison self-check, CLI help, GitHub Raw CORS/header probe.
- **Open issues:** Real SSH/IBM-host acceptance requires the user's configured `cmtest` target and key; HTTP Basic Auth is appropriate only for the confirmed trusted LAN.
- **Next action:** Configure `config.toml` and restricted root key on the deployment servers, then run physical acceptance with `ibm-patchwatch serve cmtest --bind <LAN-IP>`.

## 2026-09-04 — Remove legacy Patchwatch flows

- **Task:** Reduce the repository to the approved remote discovery → temporary LAN browser checker architecture and replace the stale README.
- **Decisions:** Keep the GitHub catalog builder/providers; remove SQLite history, terminal reports/watch mode, systemd timer, local collector web UI, and their tests. Central CLI exposes only `serve`; central package and collector versions are aligned at `0.5.0`.
- **Tests run:** full pytest, Python compileall, collector help, and central CLI help.
- **Open issues:** Physical SSH/LAN acceptance remains `NOT_RUN` until deployment.
- **Next action:** Install using the two-host procedure in `README.md`, then run physical acceptance.
