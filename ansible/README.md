# IBM-Updates mit Ansible

Manuell heruntergeladene Archive werden aus `ibm_patch_directory` gelesen.
Die Rolle lädt nichts herunter und benötigt weder HTML-Seite noch Discovery-JSON.

| Aktion | Einstieg |
| --- | --- |
| Dateien erfassen und nach Produkt zuordnen | `playbooks/scan_patches.yml` |
| Pakete auf einem ausgewählten Server installieren | `playbooks/install_patches.yml` — [Installationsanleitung](INSTALLATION.md) |
| WAS-Bestand oder Repository gezielt prüfen | [Optionale WAS-Diagnose](docs/was-diagnostics.md) |

## Einrichtung auf dem Controller

Python **3.12** auf Controller und Zielhost bereitstellen. Das System-Python wird
nicht ersetzt. Für Installationen werden administrative SSH-Rechte und der
jeweilige Installationseigentümer benötigt. Ein reiner Controller-Scan benötigt
keine Verbindung zum IBM-Server.

Aus dem Repository-Verzeichnis:

```bash
cd ansible
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-controller.txt
mkdir -p private
cp -R inventories/example/. private/
cp examples/install-was.yml private/install.yml
```

In `private/hosts.yml` die vier Beispielserver HB_TEST, HB_PROD, NDD_TEST und
NDD_PROD anpassen; SSH-Benutzer und Python-Pfad stehen in
`private/group_vars/ibm_servers.yml`. Produktparameter gemäß
[Installationsanleitung](INSTALLATION.md) eintragen. Für weitere Produkte dient
`examples/install-native.yml` als Vorlage.

Abhängigkeiten werden bei der Einrichtung installiert. Für einen isolierten
Controller vorhandene interne Paketquellen verwenden. Private Inventare,
Response-Dateien, Archive und Protokolle gehören nicht ins öffentliche Repository.

## Heruntergeladene Pakete scannen

Die eigenständige Rolle `roles/ibm_patch_scan/` erkennt die 17 benannten Dateien aus
CM FP5, ICN IF12, ICCSAP JRE/Binaries, WAS FP/iFix, IM, Java und Db2. Sie berechnet
SHA-256 und liefert `ibm_patch_scan_result`. Unbekannte Archive, doppelte Dateinamen,
leere Dateien und abgelehnte Links bleiben sichtbar. Es wird nichts entpackt oder
installiert. Dateinamen sind Hinweise; WAS-iFix-Präfixe sind keine Installationsreihenfolge.

Die Inventory-Vorlage enthält genau **HB_TEST, HB_PROD, NDD_TEST und NDD_PROD**,
mit Gruppen `hb`, `ndd`, `test`, `production`. Beispieladressen und Benutzer ersetzen.
`group_vars/ibm_servers.yml` beim Kopieren mitnehmen. Pro Host lassen sich Verzeichnis
und Scan-Ort überschreiben. Standard: Controller; dafür ist keine SSH-Verbindung nötig.
Mit `ibm_patch_scan_location: target` wird das Verzeichnis auf dem Ziel über SSH gelesen;
dort sind Python 3.12 und entsprechende Leserechte erforderlich.

```bash
ansible-playbook -i private/hosts.yml playbooks/scan_patches.yml \
  --limit HB_TEST -e ibm_patch_directory=/srv/ibm-updates \
  -e ibm_patch_report_directory="$PWD/private/reports"
```

`ibm_patch_scan_recursive: false` beschränkt den Scan auf dieses Verzeichnis.
Bei gleichem Controller-Verzeichnis genügt ein Host für den Scan. Der Bericht enthält
Dateipfade und Prüfsummen. Die Installationsrolle übernimmt den Scan selbst;
ein manuelles Abschreiben der Hashes ist für sie nicht erforderlich.
Unbekannte oder abgelehnte Dateien werden niemals automatisch zur Installation gewählt.
Eine berechnete Prüfsumme belegt keine IBM-Herkunft.

Optional YaCompress bei der Controller-Einrichtung installieren und beim Scan aktivieren:

```bash
ansible-galaxy collection install -r requirements-yacompress.yml
ansible-playbook -i private/hosts.yml playbooks/scan_patches.yml \
  --limit HB_TEST -e ibm_patch_directory=/srv/ibm-updates \
  -e ibm_patch_verify_with_yacompress=true
```

Auf dem Scan-Host müssen passende native Werkzeuge vorhanden sein, z. B. `unzip`,
`tar` und `gzip`. Ein fehlerhaftes Archiv bricht diese optionale Prüfung ab.
Ein erfolgreicher Archivtest ersetzt keine IBM-Paketprüfung.

## Nicht kumulative iFixes einzeln verlangen

Mit `ibm_patch_required_filenames` lässt sich eine ausdrücklich ausgewählte Liste
lokaler Dateien prüfen. Die Rolle liefert alle Einträge in `selected_packages`;
fehlende, unbekannte und mehrdeutige Dateien führen zum Abbruch. Sie reduziert die
Liste weder auf den höchsten IF noch auf einen APAR pro Produkt. Ohne Soll-Liste
bleibt es beim vollständigen Scan, ohne Vorauswahl.

```bash
ansible-playbook -i private/hosts.yml playbooks/scan_patches.yml \
  --limit HB_TEST -e ibm_patch_directory=/srv/ibm-updates \
  -e @examples/required-was-fixes.yml
```

Die Beispiel-Dateiliste bezieht sich auf die Vorbereitung für WAS 9.0.5.28.
Sie ist keine automatische Installationsfreigabe oder Reihenfolge. Fix Packs und
iFixes bleiben getrennt. Nach einem Basis-Update ist jeder gewünschte APAR erneut
gegen Zielbasis und IBM-Metadaten zu prüfen. Ein höherer iFix ersetzt andere nicht.
Nur eine ausdrücklich dokumentierte IBM-Ablösung darf im Installationsplan berücksichtigt
werden; der Scanner entfernt oder überspringt auch solche Pakete nicht selbst.
Beispiel: IBM verlangt bei DT496947 die vorherige Entfernung von PH71590, falls installiert.

Die Basis-/iFix-Zuordnung der Webseite verwendet separat datierte IBM-Referenzen.
Ansible bleibt davon unabhängig und vertraut weder dem Katalog noch dem Dateipräfix
als Nachweis der Installierbarkeit.

## Produktbezogene Tasks und Paketübersicht

Alle Downloads können gemeinsam unter `ibm_patch_directory` liegen; Standard ist
`/srv/ibm-updates` auf dem Controller. Den Pfad zentral in
`inventories/example/group_vars/ibm_servers.yml` beziehungsweise der privaten Kopie
oder pro Host überschreiben. Der Scan liest den Ordner genau einmal je ausgewähltem Host.

Die Rolle gliedert sich in `validate.yml`, `scan.yml`, verständlich benannte
Produktdateien unter `tasks/products/` und `report.yml`:

| Task-Datei | Getrennte Paketgruppen |
| --- | --- |
| `installation_manager.yml` | Installation-Manager-Installer |
| `db2.yml` | Db2 Published Updates / Special Builds |
| `websphere.yml` | Fix Packs und alle unabhängigen iFixes |
| `ibm_java.yml` | Java-SDK für WAS |
| `content_manager.yml` | CM-Fix-Pack-Medien |
| `content_navigator.yml` | ICN-Interim-Fix-Medien |
| `iccsap.yml` | Eingebettete JRE und Binaries-iFixes |

```bash
cd ansible
ansible-playbook -i private/hosts.yml playbooks/scan_patches.yml \
  --limit HB_TEST \
  -e ibm_patch_directory=/srv/ibm-updates \
  -e ibm_patch_report_directory="$PWD/private/reports"
```

Ergebnisse: `HB_TEST-patches.json` enthält den vollständigen Scan,
`HB_TEST-product-plan.json` die Produktübersicht. Im Playbook stehen
`ibm_patch_scan_result`, `ibm_patch_products` und `ibm_patch_plan` zur Verfügung.
Die Sortierung ist logisch: Dateien werden nicht verschoben, kopiert oder entpackt.
Jeder Eintrag behält Originalpfad, Dateigröße, SHA-256 und erkannte Metadaten.
`packages_by_kind` trennt die Paketarten; `selected_filenames` enthält nur die
explizit verlangte Soll-Dateiliste. Auch mehrere Versionen und alle iFixes bleiben erhalten.

`no_local_packages` bedeutet ausschließlich, dass für dieses Produkt keine Medien
gefunden wurden. Daraus wird nicht auf den installierten Produktbestand geschlossen.
Unbekannte Archive, Duplikate und abgelehnte Dateien stehen separat im Bericht.
Eine optionale erfolgreiche YaCompress-Prüfung gilt nur für die erfassten Archive.

Diese Übersicht bereitet die Prüfung vor. Sie ist noch kein ausführbarer
Installationsplan: Ist-Inventar, Offering-IDs, Voraussetzungen und Supersedence
werden nicht aus Dateinamen abgeleitet. Daher bleiben `applicability: not_verified`
und `installation_actions: []` ausdrücklich gesetzt. Download und Installation
werden durch dieses Playbook nicht ausgelöst. Berichte haben Modus 0600, das
Berichtsverzeichnis 0700. Ein identischer Wiederholungslauf verändert nichts.

## Entwicklung

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
ansible-playbook -i inventories/example/hosts.yml playbooks/scan_patches.yml --syntax-check
ansible-playbook -i inventories/example/hosts.yml playbooks/install_patches.yml --syntax-check
ansible-playbook -i inventories/example/hosts.yml playbooks/preflight_was.yml --syntax-check
ansible-playbook -i inventories/example/hosts.yml playbooks/stage_was.yml --syntax-check
```

CI prüft Scan, Installer, Wiederholungen, Fehler und WAS-Diagnose mit synthetischen
Medien. Eine reale IBM-/SLES-Abnahme bleibt vor dem Produktionseinsatz erforderlich.
