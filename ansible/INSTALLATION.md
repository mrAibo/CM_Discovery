# Heruntergeladene IBM-Updates installieren

Der Ablauf ist: Updates anhand der HTML-Seite auswählen, **manuell von IBM
herunterladen**, in einen Ordner auf dem Ansible-Controller legen und anschließend
`install_patches.yml` starten. Die Installation benötigt weder HTML noch
Discovery-JSON, Katalogabruf, Downloadskript oder einen vorherigen Staging-Lauf.

## Einmalige Einrichtung

Controller gemäß [README](README.md#einrichtung-auf-dem-controller) einrichten.
Python **3.12** muss auf Controller und Ziel vorhanden sein. Das Inventory enthält
HB_TEST, HB_PROD, NDD_TEST und NDD_PROD; echte Adressen, SSH-Benutzer und Interpreter
in `private/hosts.yml` eintragen. Die Rolle benötigt administrative Rechte und
führt die Installer als den angegebenen Installationseigentümer aus.

`examples/install-was.yml` oder `examples/install-native.yml` nach
`private/install.yml` kopieren. Nur gewünschte Produkte behalten und Platzhalter
ersetzen. Mehrere Produkte stehen gemeinsam unter **einer** `ibm_install_jobs`-Liste.
Anzugeben sind die vorhandene Installation, ihr Benutzer, tatsächliche Dienste,
Response-Dateien und Befehle zur Prüfung des gewünschten Produktstands. Diese
serverabhängigen Angaben lassen sich nicht aus einem Download-Dateinamen ableiten.

```yaml
# Downloadordner auf dem Controller; rekursiver Scan gemäß Scan-Einstellungen.
ibm_patch_directory: /srv/ibm-updates
# Separates Arbeitsverzeichnis auf dem Ziel; keine bestehende Installation verwenden.
ibm_install_stage_directory: /srv/ibm-install
ibm_install_target: HB_TEST
ibm_install_expected_fqdn: hb-test.example.invalid
```

## Starten

Im Verzeichnis `ansible/` mit aktivierter Python-Umgebung:

```bash
ansible-playbook -i private/hosts.yml playbooks/install_patches.yml \
  --limit HB_TEST -e @private/install.yml
```

**Dieser Befehl installiert tatsächlich.** Kein zusätzlicher Installationsschalter
und keine weitere Freigabedatei. Der separate `scan_patches.yml`-Aufruf bleibt
lesend. Installation erfolgt auf genau einem Host pro Aufruf; keine gleichzeitige
Aktualisierung beider Produktionsumgebungen. `--check` ist hier kein Probelauf und
wird abgelehnt, da die IBM-Installer keinen einheitlichen Check-Modus anbieten.

Ohne `files` im Produktauftrag werden alle erkannten Archive dieses Produkts aus
dem Ordner zugeordnet. WAS nimmt Java-Medien hinzu, wenn `com.ibm.java.jdk.v8`
in `offerings` steht. Alternativ grenzt `files` die Auswahl auf exakte Dateinamen
ein. So können ältere Pakete im Downloadordner bleiben. Mehrere widersprüchliche
Basisversionen werden nicht durch Raten aufgelöst; Downloadordner bzw. Auswahl
muss den gewünschten Stand eindeutig bestimmen. Unbekannte Dateien werden gemeldet,
nicht ausgeführt; fehlende oder doppelte ausgewählte Dateinamen führen zum Abbruch.

Der Scan sortiert logisch nach Produkt. Auf dem Server liegt jedes Archiv in
einem eigenen Verzeichnis; vorhandene Download-Dateien werden nicht verschoben.
SHA-256 wird beim Scan berechnet und nach der Übertragung erneut geprüft. Das
bestätigt die unveränderte Kopie, nicht die Herkunft des Downloads.

## Produktbezogene Installation

Die verständlichen Einstiegstasks stehen unter
`roles/ibm_ecm_install/tasks/products/`. Gemeinsame Ausführung und Protokollierung
liegen im Modul `library/ibm_install_product.py`.

| Produkt | Installationsweg |
|---|---|
| Installation Manager | `installc` als root bzw. `userinstc` für eine vorhandene benutzereigene Installation |
| Db2 | `installFixPack -b <Kopie> -y`, anschließend explizites `db2iupdt` für jede konfigurierte Instanz |
| WAS und Java | `imcl install` mit vollständigen Offering-Versionen aus den getrennten lokalen Repositories; anschließend jeder gewählte iFix |
| Content Manager | Im Archiv gefundenes `installUpdate -i silent -f <Response-Datei>` |
| Content Navigator | Im Archiv gefundener Linux-Installer mit `-f <Response-Datei>`; Konfiguration/Build/Deployment über `after` |
| ICCSAP | Konkrete Befehle der Paket-Readmes über `commands`, für JRE und Binaries getrennt; alternativ `engine: imcl` bei einem tatsächlich vorhandenen IM-Repository |

Die Reihenfolge ist IM → Db2 → Java/WAS → CM → ICN → ICCSAP; nur ausgewählte
Produkte werden ausgeführt. Dies ersetzt keine Prüfung der unterstützten
Produktkombination oder der Abhängigkeiten einer verteilten ECM-Installation.
Insbesondere müssen alle Nutzer einer Db2-Kopie vor dem Update stillgelegt sein.

Jeder Produktauftrag hat dieselbe Reihenfolge:

1. Medien, Installer und lesende Versionsabfragen **für alle Produkte** vorbereiten.
2. Vorhandenen Zielstand prüfen; bei bereits vollständig erreichtem Stand nur
   Funktionstests ausführen und Installation überspringen.
3. `before` ausführen, anschließend `stop_services` in Listenreihenfolge stoppen.
4. Produktinstaller ausführen, danach `after` für Konfiguration/Deployment.
5. Zielstand über `verify` nachweisen, `start_services` starten, `healthchecks` ausführen.

`before`, `after`, `verify` und `healthchecks` enthalten `argv`-Listen mit absoluten
Programmpfaden. Optional: `user`, bei Installationsschritten auch `environment`,
`cwd`, `success_rc` und ein erwartetes Ausgabemuster `match`. Es wird keine Shell
implizit gestartet. `{media}` bzw. `{archive}` referenziert das erste Medium;
`{media:DATEINAME}` bzw. `{archive:DATEINAME}` ein bestimmtes Medium. Native
Installer laufen aus ihrem eigenen Verzeichnis. Keine Passwörter in Befehlsargumenten;
Response-Dateien bleiben privat und sollten aus der eigenen gesicherten Ablage kommen.

Die lesenden `verify`-Befehle müssen auch beim alten Stand erfolgreich abfragen
können; der reguläre Ausdruck unterscheidet alt und Ziel. Ein nicht erfolgreicher
Abfragebefehl ist ein Fehler, kein Beleg für eine fehlende Installation. Prüfungen
müssen den **vollständigen gewünschten Stand** erfassen: etwa Db2 Special Build
statt nur `11.5.9`, beide ICCSAP-Komponenten sowie konfigurierten/deployten ICN-Stand.
Andernfalls könnte ein bereits aktuelles Binärpaket notwendige Folgearbeiten überspringen.

## WAS-iFixes und Supersedence

`offerings` enthält beispielsweise `com.ibm.websphere.BASE.v90` oder
`com.ibm.websphere.ND.v90` und **`com.ibm.java.jdk.v8`**. Die Rolle prüft, dass diese
Offerings in der angegebenen Installation vorhanden sind, und verlangt eine
eindeutige Zielversion aus den ausgewählten Medien. Basis/SDK werden mit
`-installFixes none` aktualisiert; iFixes folgen einzeln über `fix_ids`.

Für jedes ausgewählte iFix-Archiv muss die exakte IM-Fix-ID aus dem Paket angegeben
sein. Sie ist nicht automatisch identisch mit APAR oder Archivnamen. Bei einem
reinen iFix-Auftrag zusätzlich `offering_id` für die vorhandene Installation setzen.
IM-IDs bzw. angebotene Fixes lassen sich nach dem Entpacken über den vorhandenen IM
ermitteln, beispielsweise mit `listAvailableFixes <Offering_ID_interneVersion>
-repositories <repository.config> -useServiceRepository false`. Diese Auflistung
allein bestätigt laut IBM noch nicht die Eignung jedes Fixes für die Installation.

Keine automatische Auswahl des numerisch höchsten iFixes. Kein Wegfiltern allein
nach dem Versionspräfix eines Archivnamens: einige für ältere FP benannte WAS-Fixes
sind auch für FP28 freigegeben. Maßgeblich bleiben die IBM-Anwendbarkeit und
Supersedence des konkreten Pakets. Zum dokumentierten Entfernen ersetzter Fixes
`remove_fix_ids` und `supersedence_source` setzen; nur aktuell installierte IDs
werden vor dem Update entfernt. Alle gewünschten Fix-IDs müssen anschließend in
der aktiven IM-Fixes-Liste stehen; Rollback-Historie zählt nicht als Installation.

`-useServiceRepository false` verhindert die automatische Nutzung des
Service-Repository. Dies ist **keine Netzwerksperre**: lokale Repository-Metadaten
können weitere Quellen referenzieren. Offline-Medien verwenden; ein vollständig
isoliertes Ziel bleibt die Netzwerkgrenze. Die Rolle lädt keine Pakete von IBM.

## Fehler, Wiederholung und Betriebsgrenzen

Eine atomare Sperre unter `/var/lock/ibm-ecm-install` verhindert parallele
Installationsläufe dieser Rolle auf demselben Host. Sie wird nach erfolgreicher
Abnahme entfernt. Bei Fehlern bleiben Sperre und Laufverzeichnis erhalten.
`run` im Sperrverzeichnis zeigt auf die Protokolle; jeder Aufruf schreibt ein
privates nummeriertes Log. Bei Erfolg entsteht zusätzlich `result.json`.

Nicht pauschal Dienste starten oder die Sperre automatisch löschen. Zuerst
Installerprozesse, Protokolle und Produktstand prüfen; bei Timeout können
Installer-Unterprozesse noch laufen. Erst nach Behebung und geklärtem Zustand
die Sperre administrativ entfernen und erneut starten. Es gibt keinen allgemeinen
IBM-Rollback: Backup und Wiederherstellung werden über den vorhandenen
produktbezogenen Wartungsablauf organisiert. Explizite `before`-/`after`-Befehle
können selbst Dienste starten; deren Fehlerbehandlung bleibt Teil dieser Befehle.

Automatisierte Tests verwenden synthetische Archive und Installer und prüfen auch
einen vollständigen Ansible-Lauf mit dem nativen CM-Aufruf, Wiederholung und Fehler.
**Es wurde kein echter IBM-Server aktualisiert.** ICCSAP-Befehle sowie CM-/ICN-
Response- und Deployment-Konfiguration müssen anhand der tatsächlich heruntergeladenen
Medien vervollständigt werden. Die Beispiele sind konfigurierbare Vorlagen, kein
fertiges Inventory für die reale Umgebung.

## IBM-Referenzen

- [IM-Kommandoargumente](https://www.ibm.com/docs/en/installation-manager/1.10.0?topic=line-command-arguments-imcl-command)
- [WAS und Java über die Kommandozeile installieren](https://www.ibm.com/docs/en/was/9.0.5?topic=offerings-installing-product-by-using-command-line)
- [WAS-iFixes installieren und entfernen](https://www.ibm.com/docs/en/was/9.0.5?topic=product-installing-uninstalling-interim-fixes)
- [Db2 Offline-Fixpack](https://www.ibm.com/docs/en/db2/11.5.x?topic=ifplu-installing-offline-fix-pack-updates-existing-db2-database-products)
- [CM 8.7 FP5 Readme](https://www.ibm.com/docs/en/content-manager/8.7.0?topic=fp-content-manager-version-87-fix-pack-5-readme)
- [ICN 3.1.0 IF012 Readme](https://www.ibm.com/support/pages/ibm-content-navigator-version-310-interim-fix-12-readme)
