# Optionale WAS-Diagnose

Diese Playbooks bleiben für eine gezielte Bestandsprüfung oder eine isolierte
IM-Repository-Abfrage verfügbar. Sie sind keine Voraussetzung für
`install_patches.yml` und verändern keine installierten IBM-Produkte.

Controller und Inventory gemäß [Ansible-README](../README.md#einrichtung-auf-dem-controller)
einrichten. Alle folgenden Befehle im Verzeichnis `ansible/` ausführen:

```bash
cp examples/change-was.yml private/change-was.yml
```

In `private/change-was.yml` die Platzhalter und erwarteten Werte ersetzen. Versionen aus
`imcl listInstalledPackages -verbose` und `versionInfo.sh` der **konkreten**
Installation übernehmen. `expected_internal_version` bezeichnet die vollständige
IM-Version in Klammern, nicht nur `9.0.5.25`. Archivpfad und SHA-256 selbst angeben:

```bash
sha256sum /srv/ibm-updates/MEIN-IBM-PAKET.zip
```

Eine selbst berechnete Prüfsumme bestätigt die Unverändertheit dieser Kopie,
nicht ihre Herkunft. IBM-Quelle und veröffentlichte Prüfsumme/Signatur, sofern
vorhanden, separat prüfen. Keine Pakete, privaten Inventare, Zugangsdaten oder
IM-Rohprotokolle in das öffentliche Repository übernehmen. `private/` ist ignoriert.

## Vorprüfung starten

Im Verzeichnis `ansible/`, mit aktivierter Umgebung:

```bash
ansible-playbook -i private/hosts.yml playbooks/preflight_was.yml \
  --limit HB_TEST -e @private/change-was.yml
```

Die Rolle prüft:

1. Pflichtfelder, Platzhalter, genau einen Host und absolute Pfade.
2. Python 3.12 auf Controller und Ziel, FQDN, SLES-Version und Architektur.
3. Existenz, regulären Dateityp, Größe größer null und SHA-256 des Controller-Archivs.
4. IM-Paket anhand **Installationsverzeichnis plus Paket-ID**; mehrere Treffer
   sind ein Fehler. Andere Installationen derselben Produkt-ID bleiben getrennt.
5. Vollständige interne IM-Version und sichtbare Produktversion.
6. Übereinstimmung mit `versionInfo.sh` aus demselben WebSphere-Verzeichnis.

Nicht erfolgreiche Lesebefehle und Zeitüberschreitungen brechen ab, auch wenn
ihre Ausgabe eine plausible Version enthält. Englische und deutsche IM- und
WAS-Ausgaben werden unterstützt; unbekannte Formate werden abgelehnt.
Die Prüfung stoppt keine Dienste und installiert keine IBM-Pakete. Ansible kann
wie üblich temporäre Moduldateien anlegen; IBM-Lesewerkzeuge können eigene
Diagnosedaten schreiben. Ausgaben sind auf Deutsch.

Ein erfolgreicher Lauf meldet **„Basisprüfung erfolgreich – keine
Installationsfreigabe“**. Er prüft noch nicht den Inhalt/Offering des Archivs,
Abhängigkeiten, iFix-Kompatibilität, freien Staging-/Backup-Speicher, Profile,
Sperren, Healthchecks oder Wiederherstellbarkeit. Er beweist weder Update-Eignung
noch vollständige Sicherheit des installierten Systems.

## Repository separat bereitstellen

Nach erfolgreicher Basisprüfung kann das bereits heruntergeladene Paket mit
`stage_was.yml` auf den Zielhost übertragen und dort geprüft werden. Dieser
Schritt ändert nur das Staging und gegebenenfalls lokale IM-Caches/Protokolle;
IBM-Software und Dienste werden nicht aktualisiert oder gestoppt.

Zusätzliche Parameter in `private/change-was.yml`:

- `target_internal_version`: exakte interne Zielversion aus dem gewählten Paket;
  kein `latest` und keine aus einer sichtbaren Versionsnummer erfundene Build-ID.
- `stage_directory`: vorhandenes dediziertes Verzeichnis auf dem Ziel, außerhalb
  der WAS-Installation, ohne Symlink, Eigentümer `installation_owner`, Modus 0700.
- `stage_reserve_bytes`: gewünschte freie Reserve in Bytes. Die Vorlage enthält
  1 GiB; vor dem Lauf passend zur Umgebung festlegen. Zusätzlich wird freier
  Platz für zweimal die ZIP-Größe verlangt. Das ersetzt keine Platzprüfung für
  die spätere Installation, Entpackung oder Sicherung. Auch Ansible-Temporärpfade
  müssen ausreichend Platz haben.

Der Staging-Lauf benötigt administrative Rechte sowie `unshare` und `runuser`
aus util-linux auf dem Ziel. Die Rolle installiert diese Programme nicht.
`unshare --net` startet die IM-Abfrage ohne externe Netzwerkverbindung;
`runuser` führt IM anschließend als Installationseigentümer aus. Fehlende Rechte
oder eine gesperrte Namespace-Funktion führen zum Abbruch. Es gibt keinen
Fallback mit Netzwerkzugriff und keine globale Änderung der IM-Präferenzen.
Die Unterstützung muss auf dem konkreten SLES-Host geprüft werden.

```bash
ansible-playbook -i private/hosts.yml playbooks/stage_was.yml \
  --limit HB_TEST -e @private/change-was.yml
```

Ablauf:

1. Basis-Vorprüfung erneut ausführen.
2. Ein vollständiges ZIP mit `repository.config` im Wurzelverzeichnis verlangen;
   doppelte Namen, verschlüsselte Einträge, Links und gefährliche Pfade ablehnen.
3. Staging-Verzeichnis und freie Kapazität prüfen.
4. Datei als `<sha256>.zip` übertragen, ohne vorhandene abweichende Dateien
   automatisch zu überschreiben. Das Archiv wird nicht entpackt.
5. SHA-256 auf dem Ziel erneut prüfen und mit IM
   `listAvailablePackages -repositories <lokales-zip>` genau das gewünschte
   `<package_id>_<target_internal_version>` bestätigen.

Ein bereits vorhandenes identisches ZIP wird wiederverwendet; die Prüfung wird
wiederholt. Bei Fehlern bleibt die übertragene Datei zur Diagnose bestehen.
Gleichzeitige Staging-Läufe mit identischem Inhalt benötigen dieselbe Datei;
das ist **keine Installationssperre**. Die eigenständige Installationsrolle verwendet ihre eigene Hostsperre.

Mehrteilige Medien, verschachtelte ZIPs, HTTP-Repositories und automatische
Auswahl der neuesten Version werden in diesem Schritt nicht unterstützt.
Die ZIP-Strukturprüfung ersetzt keine vollständige Validierung aller Nutzdaten.
Ein Treffer in der IM-Liste beweist das Vorhandensein des Offering, aber nicht
Plattform-Kompatibilität, alle erforderlichen Basis-Medien oder Installierbarkeit.
Bei fehlenden Informationen erfolgt keine Installationsfreigabe.
`stage_was.yml` unterstützt absichtlich keinen `--check`-Durchlauf; verwenden Sie
für die lesende Basisprüfung `preflight_was.yml`.

Die IM-Schnittstelle ist in der offiziellen Dokumentation beschrieben:
[Repository-Inhalte mit imcl auflisten](https://www.ibm.com/docs/en/installation-manager/1.9.2?topic=line-listing-repository-contents-by-using-imcl-command).
Die Abnahme des konkreten IBM-ZIP auf SLES steht weiterhin aus.
