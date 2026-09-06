# IBM-Updates mit Ansible

Eigenständige Automatisierung für bereits lokal vorhandene IBM-Pakete.
**Aktueller Stand: Basis-Vorprüfung für WebSphere, noch keine Installation.**
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

## Nächster Ausbauschritt

Nach Sichtung eines realen WAS-Pakets mit Readme: exakte Ziel-Offering-Version,
lokales Repository, vorhandene iFixes, Dienstplan und Recovery festlegen. Danach
separates `install_was.yml` implementieren, das unmittelbar vor Änderungen erneut
prüft, sperrt, überträgt, installiert und das Ergebnis verifiziert. Kein
`perform_installation=true`-Schalter und kein Installationsaufruf aus Patchwatch.
BASE und ND lassen sich im Preflight erkennen; ein späterer Installer benötigt
für ND/Cluster eine eigene geprüfte Prozedur.

Der bisherige Collector bleibt ein optionaler Bericht. Sein globales Mapping
nach Produkt-ID wird nicht für diese Rolle verwendet. Das neue Prüfmodul enthält
keinen Import aus `src/ibm_patchwatch` und keine Abhängigkeit von Python 3.6.

## Entwicklung

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
ansible-playbook -i inventories/example/hosts.yml playbooks/preflight_was.yml --syntax-check
```

CI prüft Modulentscheidungen, echten Ansible-Modultransport mit synthetischen
IBM-Kommandos, abgelehnte Platzhalter/Zielhosts und Ansible-Syntax mit Python 3.12. Eine reale
SSH-/IBM-Abnahme steht aus; synthetische Tests ersetzen sie nicht.
