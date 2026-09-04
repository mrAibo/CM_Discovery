# Project Log

## 2026-09-04 — Remote LAN update checker v0.1

- **Task:** Move the temporary update-check UI to the internet-enabled central Linux server, using fresh remote SSH discovery from the IBM Content Manager host.
- **Decisions:** Collector remains `/root/bin/ibm_discovery.py`; central `ibm-patchwatch serve` owns SSH and LAN HTTP; Basic Auth defaults to `admin/admin` with environment overrides; browser reads the public GitHub catalog directly; inventory never leaves the LAN; comparisons fail closed; DB2 special builds are not numerically ranked.
- **Files changed:** `src/ibm_patchwatch/web.py`, `src/ibm_patchwatch/cli.py`, `tests/test_web.py`, `README.md`, `docs/plans/2026-09-04-remote-lan-update-checker-design.md`.
- **Tests run:** focused pytest, full pytest, Python compileall, git diff check, Node comparison self-check, CLI help, GitHub Raw CORS/header probe.
- **Open issues:** Real SSH/IBM-host acceptance requires the user's configured `cmtest` target and key; HTTP Basic Auth is appropriate only for the confirmed trusted LAN.
- **Next action:** Configure `config.toml` and restricted root key on the deployment servers, then run physical acceptance with `ibm-patchwatch serve cmtest --bind <LAN-IP>`.
