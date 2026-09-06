# IBM-Updates mit Ansible

Eigenständige Automatisierung für bereits lokal vorhandene IBM-Pakete.
**Aktueller Stand: Basis-Vorprüfung und Repository-Staging für WebSphere, noch keine Installation.**
Die Rolle lädt nichts herunter und benötigt weder Patchwatch noch dessen Katalog.

## Voraussetzungen

- Python **3.12** auf Controller und Zielhost; die Rolle prüft beide Versionen.
- `ansible-core` 2.20.8 auf dem Controller (siehe `requirements-controller.txt`).
- Python 3.12 auf dem Ziel bereits eingerichtet, zum Beispiel zusätzlich unter
  `/usr/bin/python3.12`. Den tatsächlichen Pfad im Inventory angeben; das
  System-Python wird nicht ersetzt und von dieser Rolle nicht installiert.
- SLES, administrative SSH-Verbindung und Wechsel zum Eigentümer der vorhandenen
  Installation Manager Installation. Der auf den Collector beschränkte
  Patchwatch-SSH-Schlüssel ist dafür ungeeignet.
- Lokales IBM-Archiv auf dem Controller, unabhängig heruntergeladen.

Python 3.12 liegt im unterstützten Bereich von ansible-core 2.20:
[Ansible-Supportmatrix](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html).
Die konkrete Python-3.12-Bereitstellung hängt von SLES-Version und Service Pack ab.

## Struktur

- `roles/ibm_was_update/`: Rolle und eigenständiges lesendes Prüfmodul.
- `playbooks/preflight_was.yml`: separater Einstieg für genau einen Host.
- `playbooks/stage_was.yml`: erneute Vorprüfung, Übertragung und lokale Repository-Abfrage.
- `inventories/example/hosts.yml`: Inventory-Vorlage.
- `examples/change-was.yml`: Vorlage für lokale Parameter.
- `tests/`: Tests für mehrfache Installationen, Versionsabweichungen und Fehler.

## Einrichtung auf dem Controller

Aus dem Repository-Verzeichnis:

```bash
cd ansible
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-controller.txt
mkdir -p private
cp inventories/example/hosts.yml private/hosts.yml
cp examples/change-was.yml private/change-was.yml
```

Installation der Controller-Abhängigkeiten erfolgt bei der Einrichtung; der
spätere Preflight benötigt keinen Internetzugang. Bei isoliertem Controller
Pakete aus dem vorhandenen internen Repository oder Wheel-Verzeichnis verwenden.

In beiden Dateien die Platzhalter und erwarteten Werte ersetzen. Versionen aus
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
  --limit cmtest -e @private/change-was.yml
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
  --limit cmtest -e @private/change-was.yml
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
das ist **keine Installationssperre**. Eine spätere Installation braucht eine
separate Sperre für den betroffenen IM-Bereich.

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

## Nächster Ausbauschritt

Für ein separates `install_was.yml` fehlen noch die Readme des tatsächlichen
Pakets, Voraussetzungen einschließlich vorhandener iFixes, Profile/Dienstplan,
Healthchecks und eine geprüfte Wiederherstellung. Erst danach die passende
Installationsprozedur implementieren. Kein `perform_installation=true`-Schalter
und kein Installationsaufruf aus Patchwatch. BASE und ND lassen sich prüfen;
für ND/Cluster ist später eine eigene geprüfte Prozedur erforderlich.

Der bisherige Collector bleibt ein optionaler Bericht. Sein globales Mapping
nach Produkt-ID wird nicht für diese Rolle verwendet. Die Prüfmodule enthalten
keinen Import aus `src/ibm_patchwatch` und keine Abhängigkeit von Python 3.6.

## Entwicklung

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
ansible-playbook -i inventories/example/hosts.yml playbooks/preflight_was.yml --syntax-check
ansible-playbook -i inventories/example/hosts.yml playbooks/stage_was.yml --syntax-check
```

CI prüft Entscheidungen, Ansible-Modultransport und Staging mit synthetischen
IBM-Dateien, abgelehnte Platzhalter/Zielhosts und beide Playbook-Syntaxen.
Ein gesperrter Netzwerk-Namespace muss auch im Test zum Abbruch der Abfrage
führen. Eine reale SSH-/IBM-Abnahme steht aus; synthetische Tests ersetzen sie nicht.
