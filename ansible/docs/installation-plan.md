# Quellen und nächster Installationsschritt

Stand: 07.09.2026. Öffentliche Readmes werden direkt bei IBM recherchiert.
Ein Scan erkennt Dateien; er beweist weder deren Herkunft noch Installierbarkeit.

| Paketfamilie | Quelle und Konsequenz |
| --- | --- |
| Content Manager 8.7 FP5 | [FP5-Readme](https://www.ibm.com/docs/en/content-manager/8.7.0?topic=fp-content-manager-version-87-fix-pack-5-readme). FP5 ersetzt die falsche FP1-/FP4-Anzeige. Bibliotheksserver, Ressourcenmanager und Datenbank gemeinsam planen. |
| Content Navigator 3.1.0 IF12 | [IBM-Readme](https://www.ibm.com/support/pages/ibm-content-navigator-version-310-interim-fix-12-readme). Installer benötigt Java 11 oder 17; Konfiguration und erneute Bereitstellung gehören zum Update. Das ist kein Austausch des WAS-Java-8-SDK. |
| WAS 9.0.5 FP28 | [FP28-Download und Voraussetzungen](https://www.ibm.com/support/pages/90528-websphere-application-server-traditional-version-90528). IM mindestens 1.8.5, vorhandenes WAS-9-Offering und passendes SDK prüfen. |
| WAS iFixes | APAR-Readme und Paketmetadaten einzeln abgleichen. Beispiel: [PH71590 / DT496947](https://www.ibm.com/support/pages/ph71590ibm-websphere-application-server-vulnerable-identity-spoofing-cve-2026-8644) beschreibt Ablösungen und konkrete FP-Bereiche. Alle neun Dateien pauschal zu installieren wäre falsch. |
| ICCSAP | JRE und Binaries IF21 getrennt erfassen. IF21 und das Base-JRE-Paket sind über die vom Betreiber bestätigten Fix-Central-Links getrennt verfügbar. Die vollständigen IF21-Voraussetzungen bleiben vor Installation zu prüfen. |
| Db2 11.5.9 | [Published Updates](https://www.ibm.com/support/pages/node/7087189). Update 87984 nach IBM-Chronologie betrachten; Special-Build-Nummern nicht numerisch als Versionsreihenfolge interpretieren. |

## Getrennte Aktionen

1. `scan_patches.yml`: vorhandene Dateien erfassen, optional Archive testen.
2. `preflight_was.yml`: eine konkrete Installation und eine ausdrücklich gewählte Datei prüfen.
3. `stage_was.yml`: das gewählte WAS-Fix-Pack-ZIP bereitstellen und Offering mit IM abfragen.
4. Noch zu implementieren: `install_was.yml` mit Installationssperre, geprüfter Sicherung,
   kontrolliertem Dienststopp, exakter Offering-Auswahl, Versionsprüfung und Healthcheck.

Der Installationslauf wird unabhängig vom Download ausgelöst. Zunächst einen Testhost
verwenden; Produktionshosts einzeln nach bestandener Abnahme. HB/NDD sind Umgebungsnamen,
kein Beleg für eine bestimmte WAS-Edition oder Cluster-Topologie. Diese Daten müssen aus
der Zielinstallation stammen. Bei Installationsfehlern Diagnose sichern und den geprüften
Wiederherstellungsplan anwenden; kein pauschales automatisches Rückspielen von Dateien.

## YaCompress

[mrAibo/ansible_yacompress](https://github.com/mrAibo/ansible_yacompress) ist als optionale
Collection angebunden, auf Commit `9ab0d250f3afe53faac4d1d7c1bdea9f11bb05aa` festgelegt.
`archive_verify` testet vorhandene ZIP-/TAR-Archive mit nativen Werkzeugen. Das prüft
Lesbarkeit, nicht die IBM-Signatur, APAR-Abhängigkeiten oder eine sichere Entpackung.
Die IBM-Archive werden nicht neu komprimiert. Für spätere Dateisicherungen können
Manifestprüfung und Komprimierung nützlich sein; eine laufende Db2-Datenbank benötigt
zusätzlich ein datenbankgerechtes Sicherungsverfahren. Lösch-/Rotationsfunktionen werden
hier nicht verwendet. Der normale Scan funktioniert ohne diese Collection.

## Verbindliche Behandlung von iFixes

Jeder iFix bleibt ein eigener Eintrag. Weder Datum noch höhere IF-/APAR-Nummer
berechtigen zum Weglassen anderer Fixes. IBM-Versionsbereiche werden separat vom
Dateipräfix gespeichert. Eine dokumentierte Ablösung wird als Beziehung behandelt,
nicht als allgemeine kumulative Eigenschaft. Vor Basis-Updates und danach den
vollständigen erforderlichen APAR-Satz prüfen. Der Scanner wählt und entfernt
keine Fixes automatisch; `ibm_patch_required_filenames` verlangt jede benannte Datei.
