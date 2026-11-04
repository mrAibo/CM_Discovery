# Ansible-Audit: install_patches.yml (Produktivsystem)

Stand: Lesender Review, nichts geändert. Pfade relativ zu `ansible/`.
Kürzel: P = `roles/ibm_ecm_install/library/ibm_install_product.py`, M = `roles/ibm_ecm_install/tasks/main.yml`.

Positiv vorab: Vorabvalidierung vor Dienststopps, Zielhost-/FQDN-Guard, exklusive mkdir-Sperre, `desired_state()`-Skip,
SHA-256 nach Transfer, sicheres Entpacken (`filter='data'`), kein automatischer Neustart bei unklarem Zustand,
argv statt Shell, ansible-core gepinnt, YaCompress auf Commit gepinnt.

## Zusammenfassung
| # | Schwere | Thema |
|---|---------|-------|
| 1 | Hoch | Prüfsumme stammt aus dem Scan selbst, kein freigegebener Soll-Hash |
| 2 | Hoch | Backup (`before`) ist Pflicht-Platzhalter, wird nicht erzwungen und läuft vor dem Dienststopp |
| 3 | Hoch | Fehler nach `systemctl stop` hinterlässt gestoppte Dienste ohne Rollback-Hinweis |
| 4 | Hoch | Sperre in `/var/lock` (tmpfs) geht beim Reboot verloren |
| 5 | Mittel | Kein Dry-Run: `--check` bricht hart ab, `validate_only` ist nicht erreichbar |
| 6 | Mittel | Teilergebnisse gehen bei Fehler in Folgeprodukt verloren (`result.json` nur am Ende) |
| 7 | Mittel | Response-Dateien und entpackte Medien bleiben dauerhaft liegen |
| 8 | Mittel | Jeder Lauf überträgt und entpackt alles neu (`changed=True` immer, Zeitstempel-Verzeichnis) |
| 9 | Mittel | Timeout lässt Kindprozesse/Installer-Zustand offen; Standard 3600 s |
| 10 | Mittel | `update-ibm-catalog.yml` pusht ungetestet direkt auf `main` |
| 11 | Niedrig | Root-Nutzung: gesamte Umgebung des Root-Prozesses wird an Installer vererbt |
| 12 | Niedrig | Sperr-Fehlermeldung kryptisch; CI ohne ansible-lint; Actions nicht per SHA gepinnt |
| 13 | Niedrig | `docs/REVIEW.md` erwähnt Ansible-Rolle nur als Restgrenze |

## 1. Hoch: Kein freigegebener Soll-Hash
`roles/ibm_ecm_install/tasks/prepare_archive.yml:36-38`, `roles/ibm_patch_scan/library/ibm_patch_scan.py:135`.
Der SHA-256 wird vom Scan auf dem Controller berechnet und danach nur gegen sich selbst geprüft. Das schützt vor
Transportfehlern, nicht vor einem falschen oder manipulierten Download. Der Hash sollte aus dem Job kommen (von IBM Fix Central notiert).
```yaml
# Vorher (prepare_archive.yml:36-38)
ibm_install_media:
  archive: ".../archive"
  sha256: "{{ install_archive.sha256 }}"      # selbst berechnet
# Nachher: Soll-Hash im Job, Abbruch bei Abweichung
- ansible.builtin.assert:
    that: install_archive.sha256 == (install_job.sha256[install_filename] | lower)
    fail_msg: "Kein freigegebener SHA-256 für {{ install_filename }} im Job."
```

## 2. Hoch: Backup nicht erzwungen, falsche Reihenfolge
`P:243-245`, `examples/install-was.yml` (`before: - argv: [/UNRESOLVED/backup-was]`), `P:validate` (`before` darf `[]` sein).
`before` läuft vor `systemctl stop`: ein Backup bei laufendem Dienst ist nicht konsistent. Ein leeres `before` wird akzeptiert,
und es gibt keine Nachweisprüfung des Backups.
```python
# Vorher (P:243-245)
self.steps(self.job['before'])
for service in self.job['stop_services']: ...stop
# Nachher
for service in self.job['stop_services']: ...stop
self.steps(self.job['backup'])             # Pflichtfeld in validate(); Ausgabe per 'match' prüfen
if not self.checks(self.job['backup_verify']): raise ValueError('Backup nicht nachgewiesen.')
```

## 3. Hoch: Fehler nach Dienststopp, kein Rollback-Hinweis
`P:244-251`, `M:107-119` (kein `rescue`), `INSTALLATION.md:141-147`.
Bewusst kein Auto-Start, aber die Fehlermeldung nennt weder gestoppte Dienste noch Backup noch Wiederherstellungsweg.
`remove_fix_ids` (P:173) deinstalliert vor der Installation; schlägt diese fehl, ist der Fix weg.
```yaml
# Vorher: Fehler bricht den Play ab, nur Log-Pfad in msg
# Nachher (M, um Produkt-Includes)
- block: [ ...Produkt-includes... ]
  rescue:
    - ansible.builtin.copy:
        content: "{{ {'failed_task': ansible_failed_task.name, 'stopped_services': install_job_stopped | default([]), 'run': ibm_install_run_directory} | to_nice_json }}"
        dest: "{{ ibm_install_run_directory }}/FAILED.json"
        mode: '0600'
      become: true
    - ansible.builtin.fail:
        msg: "Abbruch. Dienste ggf. gestoppt. Backup/Restore: {{ ibm_install_run_directory }}/FAILED.json, Lock {{ ibm_install_lock_directory }} bleibt."
```
Zusätzlich im Modul `stopped_services` in das `fail_json(...)` aufnehmen (P:265).

## 4. Hoch: Sperre überlebt keinen Reboot
`defaults/main.yml` (`ibm_install_lock_directory: /var/lock/ibm-ecm-install`), `M:71-75`, `INSTALLATION.md:135`.
`/var/lock` ist tmpfs. Nach Absturz/Reboot mitten im Patchen (z.B. Installer-Crash) ist die Sperre weg, das Laufverzeichnis
(`/srv/ibm-install/<ts>`) bleibt, ein Zweitlauf startet auf halb gepatchtem System.
```yaml
# Vorher
ibm_install_lock_directory: /var/lock/ibm-ecm-install
# Nachher (persistentes Dateisystem)
ibm_install_lock_directory: /var/lib/ibm-ecm-install/lock
```
(Elternverzeichnis vorab mit 0700 root anlegen; Assertion in `M:5-13` erweitern, dass der Pfad nicht unter `/run`, `/var/lock`, `/tmp` liegt.)

## 5. Mittel: Kein Dry-Run, Check-Mode nur Abbruch
`M:5`, `playbooks/install_patches.yml:4-11`, `P:236-238`, beide Module `supports_check_mode=False`.
`--check` schlägt per Assert fehl. Der vorhandene `validate_only`-Pfad läuft nur intern als Vorprüfung nach dem Kopieren/Entpacken.
Ein Bediener kann nicht ohne Änderung prüfen.
```yaml
# Vorher (M:5)
- not ansible_check_mode
# Nachher: Check-Mode erlauben, nur Prüfungen (Scan, Hash, Zielguard) laufen; Schreibtasks
# bekommen "when: not ansible_check_mode", Ende mit klarer Meldung
- ansible.builtin.meta: end_host
  when: ansible_check_mode or (ibm_install_validate_only | default(false))
```

## 6. Mittel: Teilergebnisse gehen verloren
`M:107-113`, `products/*.yml` (`ibm_install_results` nur im Speicher).
Schlägt Produkt 3 fehl, ist nirgends dokumentiert, dass Produkt 1+2 bereits installiert wurden (`any_errors_fatal` bricht ab).
```yaml
# Vorher (products/websphere.yml:12-14): nur set_fact
# Nachher: je Produkt sofort persistieren
- ansible.builtin.copy:
    content: "{{ ibm_install_results | to_nice_json }}\n"
    dest: "{{ ibm_install_run_directory }}/result.json"
    mode: '0600'
  become: true
```

## 7. Mittel: Response-Dateien und Medien bleiben liegen
`prepare_product.yml` (Response-Kopie nach `.../response.rsp`), `M:115-119`.
Nach Erfolg wird nur die Sperre entfernt; Response-Dateien (können Passwörter enthalten), Archive und Payload (mehrere GB) bleiben.
```yaml
# Nachher, nach Sperrfreigabe
- ansible.builtin.find: {paths: "{{ ibm_install_run_directory }}", patterns: ['response.rsp', 'archive'], recurse: true}
  become: true
  register: ibm_install_cleanup
- ansible.builtin.file: {path: "{{ item.path }}", state: absent}
  loop: "{{ ibm_install_cleanup.files }}"
  become: true
# oder: shred für response.rsp, Payload nach Aufbewahrungsfrist löschen
```

## 8. Mittel: Idempotenz nur auf Produktebene
`M:49-51`, `ibm_install_media.py:84` (`changed=True` immer), `prepare_archive.yml:28-40`.
`desired_state()` verhindert die Neuinstallation, aber jeder Lauf kopiert und entpackt alle Archive neu in ein neues
Zeitstempelverzeichnis, obwohl das Produkt schon aktuell ist. Prüfen Sie `desired_state` vorab (validate_only mit Zielstand).
```yaml
# Nachher: Vorabprüfung, Archive nur bei Bedarf übertragen
- ibm_install_product: {job: ..., media: {}, validate_only: true, check_target_state: true}
  register: pre
- include_tasks: prepare_archive.yml
  when: pre.status != 'already_installed'
```

## 9. Mittel: Timeout
`P:110-112`: `subprocess.run(..., timeout=3600)` beendet nur den direkten Kindprozess; IM/Db2-Subprozesse laufen weiter,
während die Meldung "Sperre bleibt" erscheint. Nachher: `Popen(..., start_new_session=True)` und bei Timeout `os.killpg`
erst nach Warnung, oder Timeout pro Schritt (`step.timeout`) und Protokoll des Abbruchs in `FAILED.json`.

## 10. Mittel: Katalog-Workflow pusht ungetestet auf main
`.github/workflows/update-ibm-catalog.yml:20-23, 52, 83-87`, `permissions: contents: write` workflowweit.
Kein pytest/Node-Test zwischen Refresh und Push; `git reset --hard` plus Direkt-Push umgeht Review; `cancel-in-progress: true` kann
mitten im Push abbrechen.
```yaml
# Vorher
      - name: Build complete portable output folder
        run: python scripts/build_static_page.py
# Nachher
      - run: python -m pip install -e . pytest && python -m pytest -q
      - run: python scripts/build_static_page.py
# und: Änderungen als PR (peter-evans/create-pull-request@<SHA>) statt Push auf main; cancel-in-progress: false
```

## 11. Niedrig: Root-Nutzung
`M:61,74,82,112,119` (`become: true` ohne `become_user` = root für alle Schreibtasks), `P:100-103`.
Root ist für systemctl und Staging nötig, aber das Modul vererbt `os.environ` (Root-Umgebung inkl. Proxy-/Ansible-Variablen)
per `runuser` an den Installer. Nachher:
```python
# Vorher (P:103)
environment = dict(os.environ, **self.job.get('environment', {}), **(env or {}))
# Nachher
environment = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', **self.job.get('environment', {}), **(env or {})}
```
Außerdem `-acceptLicense` ist hart verdrahtet (P:173-179); als Job-Flag `accept_license: true` explizit machen.

## 12. Niedrig: Kleinigkeiten
- `M:73` Sperre existiert: kryptischer mkdir-Fehler. Nachher:
  `failed_when` mit `msg: "Sperre {{ ibm_install_lock_directory }} existiert: laufender oder abgebrochener Lauf, siehe {{ ibm_install_lock_directory }}/run"`.
- `.github/workflows/tests.yml:64-77`: nur `unittest` und `--syntax-check`; kein `ansible-lint`. Nachher: `pip install ansible-lint` und
  `ansible-lint ansible/playbooks ansible/roles` als Schritt.
- Actions per Tag (`actions/checkout@v4`, `tests.yml:17`; `update-ibm-catalog.yml:25`) statt Commit-SHA; `pip install -e . pytest` ungepinnt (`tests.yml:27`).
- `playbooks/install_patches.yml:7` `any_errors_fatal` bei `hosts: ibm_servers` ist nur durch das Assert in `M:6` (genau ein Host) abgesichert;
  das ist richtig, aber `serial: 1` zusätzlich setzen.
- `ibm_install_media.py:53,63`: Platzprüfung nutzt deklarierte Größen (Zip-Bomb-Risiko gering, Quelle vertrauenswürdig).

## 13. Niedrig: docs/REVIEW.md
`docs/REVIEW.md:59-62` benennt korrekt, dass keine Produktionsfreigabe vorliegt, behandelt aber nur Patchwatch (Zeilen 1-54).
Die oben genannten Punkte 2-4 sollten als "Verbleibende Grenzen" ergänzt werden; die Aussage "synthetische Tests"
sollte auf Abnahme-Checkliste (Backup nachgewiesen, Restore getestet, Sperre persistent) verweisen.

## Ungeprüft
Die vier `*_was`-Playbooks und `ibm_was_update` wurden nur auf Auffälligkeiten gelesen (Staging ist sauber: `force: false`, Hash-Assert, 0700-Prüfung);
`ibm_patch_scan`-Produkt-Tasks, Unit-Tests und die Python-Provider unter `src/` nicht. Nichts ausgeführt.
