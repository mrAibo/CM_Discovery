# IBM Patchwatch — Versionsstände und Updates

IBM Patchwatch zeigt installierte IBM-Produkte und die anhand offizieller
IBM-Quellen bestätigten Updates in einer Tabelle. Der empfohlene Ablauf besteht
aus dem vorhandenen Offline-Collector und **einer portablen HTML-Datei mit
deutscher Oberfläche**.

Öffnen Sie [IBM-Patchwatch.html](docs/IBM-Patchwatch.html) im Browser und wählen
Sie Ihre `inventory.json` aus. Der eingebettete Katalog ist auch ohne Inventar
sichtbar. Auf Windows genügt ein aktueller Browser mit aktiviertem JavaScript.

## Schnellstart: portable HTML-Datei

1. Öffnen Sie [docs/IBM-Patchwatch.html](docs/IBM-Patchwatch.html) auf GitHub und
   speichern Sie die Datei über **Download raw file** auf dem Windows-Rechner.
   Öffnen Sie die heruntergeladene Datei im Browser.
2. Erzeugen Sie auf dem CM-Server das Inventar. Aus dem Repository-Verzeichnis:

   ```bash
   python3 collectors/ibm_discovery.py --json > inventory.json
   ```

   Liegt der einzelne Collector bereits unter `/root/bin`, verwenden Sie:

   ```bash
   python3 /root/bin/ibm_discovery.py --json > inventory.json
   ```

3. Übertragen Sie die JSON-Datei über einen vorhandenen Dateitransferweg nach
   Windows. Klicken Sie in der Seite auf **inventory.json öffnen**.
4. Prüfen Sie die Produktzeilen und öffnen Sie die IBM-Links. Einige führen zur
   konkreten Fix-Auswahl, andere zur Downloadseite oder zur Produktauswahl in
   Fix Central. Plattform, IBMid-Anmeldung, Berechtigungen und Lizenzannahme
   werden auf der IBM-Seite behandelt.

Die Seite verarbeitet die ausgewählte Datei im Browser und lädt sie nicht hoch.
Sie enthält CSS, JavaScript und Katalogdaten vollständig eingebettet und ruft
selbst keine Netzwerkressourcen ab. IBM-Links öffnen sich in einem neuen Tab.
Das Inventar bleibt nur im Arbeitsspeicher dieser Seite. **Inventar ausblenden**
entfernt es aus dem Vergleich; beim Schließen der Seite wird es verworfen.

## Voraussetzungen

| Aufgabe | Voraussetzungen |
| --- | --- |
| HTML-Datei unter Windows verwenden | Aktueller Browser; Internetzugang für die IBM-Downloadseiten |
| Installierte Produkte auf dem CM-Server erfassen | Linux, Python 3.6+, lokale IBM-Kommandos und ausreichende Leserechte |
| HTML-Datei aus einem vorhandenen Katalog erzeugen | Python 3.6+, nur Standardbibliothek; Repository mit `web/` und `data/ibm/` |
| Katalog aus IBM-Quellen aktualisieren | Python 3.11+ und Zugriff auf IBM; der GitHub-Workflow verwendet Python 3.12 |
| Optionales zentrales LAN-Prüfprogramm betreiben | Python 3.11+, Git/OpenSSH und SSH-Zugriff auf den CM-Server |

Der CM-Server benötigt für die Erfassung keinen Internetzugang. Der Collector
verwendet die in `collectors/ibm_discovery.py` unter `P` hinterlegten Pfade,
beispielsweise für `cmlevel`, `db2level`, WebSphere `versionInfo.sh`, ICN
`version.txt` und Installation Manager. Prüfen Sie diese Pfade für Ihre Umgebung.
Die vorhandene zentrale SSH-Konfiguration verwendet root; der Collector selbst
erzwingt keine bestimmte Benutzerkennung. Fehlende Rechte oder Pfade müssen im
Discovery-Ergebnis beachtet werden.

## Katalog und HTML aktualisieren

Der Workflow **Refresh IBM metadata catalog** ist täglich für **03:17 UTC**
geplant. Er kann auf GitHub auch über **Run workflow** gestartet werden und läuft
zusätzlich bei den im Workflow definierten Quellcode- und Release-Ereignissen.
Er aktualisiert `data/ibm/catalog.json`, erzeugt danach
`docs/IBM-Patchwatch.html` neu und übernimmt beide Dateien in `main`.

Ist eine IBM-Quelle nicht erreichbar, bleibt ein vorhandener Katalogeintrag mit
seinem bisherigen Abrufdatum und einem Fehlerhinweis erhalten. Fehlt für eine
fehlgeschlagene Quelle ein früherer Eintrag, bricht der Workflow ab. Ein
teilweise aktualisierter Katalog mit erhaltenen Einträgen kann veröffentlicht
werden; die betroffenen Zeilen verlangen eine Prüfung.

**Eine bereits heruntergeladene HTML-Datei aktualisiert sich beim Öffnen nicht.**
Laden Sie eine neue HTML-Datei herunter oder wählen Sie unter
**Bedienung und Aktualisierung** die Schaltfläche **catalog.json öffnen**.
Quellendaten, die älter als 72 Stunden sind, und fehlgeschlagene Aktualisierungen
werden gekennzeichnet.

Nur die HTML-Datei aus dem vorhandenen Katalog neu erzeugen:

```bash
python3 scripts/build_static_page.py
```

Der Builder benötigt weder die installierte zentrale Anwendung noch einen
Internetzugang. Um auf einem Rechner mit IBM-Zugriff auch den Katalog zu
aktualisieren, verwenden Sie dort Python 3.11 oder neuer:

```bash
PYTHONPATH=src python3 scripts/update_ibm_catalog.py
python3 scripts/build_static_page.py
```

Für einen privaten Bericht mit eingebettetem Inventar:

```bash
python3 scripts/build_static_page.py --inventory /private/inventory.json --output /private/IBM-Patchwatch-report.html
```

Dieser Bericht enthält Serverdaten und gehört nicht ins Repository. Der Builder
verhindert, dass `--inventory` in die öffentliche Ausgabedatei
`docs/IBM-Patchwatch.html` geschrieben wird. Die automatisch erzeugte öffentliche
HTML-Datei enthält ausschließlich Katalogdaten und Hinweise.

## Bedeutung des Vergleichs

| Anzeige in der portablen Seite | Bedeutung |
| --- | --- |
| Neuerer Stand verfügbar / Neuerer iFix verfügbar | In derselben Versionslinie ist ein neuerer Stand bekannt; Voraussetzungen vor Installation prüfen |
| Version / iFix / Update stimmt überein | Der konkret verglichene Stand passt zum Katalog; keine Gesamtaussage über alle Sicherheitskorrekturen |
| Fix Pack stimmt überein | WAS-Fix-Pack passt; einzelne iFixes wurden nicht geprüft |
| Fix Pack gleich · iFix prüfen | CM-Fix-Pack passt; einzelne Interim Fixes lassen sich so nicht bestätigen |
| Special Build prüfen | Db2-Builds unterscheiden sich; ihre Nummern ergeben keine zeitliche Reihenfolge |
| In ICN enthalten | Daeja wurde als mitgelieferte ICN-Komponente erfasst und ist mit dem ICN-Paket zu prüfen |
| Mitgelieferte JRE prüfen | Für ICCSAP fehlt eine gemessene JRE-Version; IM-Datumskennungen reichen nicht aus |
| Andere Versionslinie / Neuer als Katalog | Kein automatischer Versionswechsel oder Downgrade wird abgeleitet |
| Katalog prüfen / Fehler bei der Erfassung | Quelle oder Erfassung ist veraltet, unvollständig, widersprüchlich oder fehlgeschlagen |
| Keine Inventardaten / Kein Katalogeintrag | Die jeweils andere Seite des Vergleichs fehlt |

Der Vergleich bleibt innerhalb der angezeigten Versionslinie. Unbekannte oder
widersprüchliche iFix- und Build-Angaben werden zur Prüfung markiert. Mehrere
Installationen derselben Produkt-ID bleiben als eigene Zeilen erhalten.

Besondere Abhängigkeiten stehen unter **Voraussetzungen und Hinweise**:
ICN 3.1 IF12 liefert laut seiner Readme Daeja 26.0.0 iFix 1 mit; sein Installer
benötigt Java 11 oder 17. Die eigenständige Daeja-5.0.15-Korrektur ist daher keine
automatische Empfehlung für die ICN-Komponente. Das SDK von WebSphere und die
mitgelieferte JRE von ICCSAP werden getrennt betrachtet.

`web/verified-notes.json` enthält fachlich geprüfte, datierte Hinweise und
Downloadlinks. Das Prüfdatum bleibt unabhängig vom Abrufdatum des Katalogs.
Versionsgebundene Hinweise werden ausgeblendet, wenn ein importierter Katalog
einen anderen Zielstand enthält. Auch die Hinweise werden nach 72 Stunden zur
erneuten Prüfung markiert; der automatische Kataloglauf aktualisiert ihren
Inhalt und ihr Prüfdatum nicht.

**Bekannte Grenze der Quellen:** Einige Provider lesen die fest hinterlegte
Readme eines bereits bekannten Releases. Ein erfolgreicher erneuter Abruf
entdeckt kein nachfolgendes Release und beweist nicht, dass der Zielstand der
neueste ist. Die Tabelle zeigt deshalb bestätigte Stände mit Quellen und Datum.
Die Suche nach neuen Releases muss für diese Provider noch um Produktindizes
oder andere belegte IBM-Metadatenquellen erweitert werden.

## Optional: vorhandenes zentrales LAN-Prüfprogramm

Der Befehl `ibm-patchwatch serve` bleibt für den bisherigen LAN-Ablauf verfügbar.
Dieser Modus verwendet eine separate englische Oberfläche und die bisherige
Vergleichslogik. Die oben beschriebenen erweiterten Statusregeln gelten für die
portable HTML-Datei. Für den empfohlenen portablen Ablauf ist der LAN-Modus
nicht erforderlich.

Im LAN-Modus erfasst ein zentraler Linux-Rechner das Inventar über SSH. Der
Windows-Browser lädt es von diesem Rechner und holt den öffentlichen Katalog
von `raw.githubusercontent.com`. IBM-Zugangsdaten bleiben auf IBM-Seiten.

### Collector und SSH vorbereiten

Auf dem zentralen Linux-Rechner:

```bash
git clone https://github.com/mrAibo/CM_Discovery.git
cd CM_Discovery
ssh root@cmserver 'mkdir -p /root/bin && chmod 700 /root/bin'
scp collectors/ibm_discovery.py root@cmserver:/root/bin/
ssh root@cmserver 'chmod 700 /root/bin/ibm_discovery.py'
ssh-keygen -t ed25519 -f ~/.ssh/id_cm_discovery -C ibm-cm-discovery
```

Den erzeugten öffentlichen Schlüssel auf dem CM-Server in
`/root/.ssh/authorized_keys` auf Quelladresse und Collector beschränken.
Ersetzen Sie die Platzhalter durch die tatsächliche LAN-IP und den vollständigen
öffentlichen Schlüssel:

```text
from="<CENTRAL_LINUX_LAN_IP>",restrict,command="/usr/bin/python3 /root/bin/ibm_discovery.py --json" ssh-ed25519 <PUBLIC_KEY_DATA>
```

Alias auf dem zentralen Rechner in `~/.ssh/config`:

```sshconfig
Host cmtest
    HostName <IBM_CM_LAN_IP_OR_NAME>
    User root
    IdentityFile ~/.ssh/id_cm_discovery
    IdentitiesOnly yes
```

Der eingeschränkte Schlüssel erlaubt nur den Collector-Aufruf. Prüfen Sie die
JSON-Ausgabe:

```bash
ssh -T cmtest | python3 -m json.tool >/dev/null
```

### Anwendung installieren und starten

Im Repository auf dem zentralen Rechner mit Python 3.11 oder neuer:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
cp config.example.toml config.toml
```

`config.toml` bleibt außerhalb von Git. Beispiel:

```toml
[ssh]
command = "ssh"
connect_timeout = 15
collector_timeout = 60

[hosts.cmtest]
collector = "/root/bin/ibm_discovery.py"
```

Den temporären Dienst starten:

```bash
. .venv/bin/activate
IBM_CHECK_USER=admin \
IBM_CHECK_PASSWORD=admin \
ibm-patchwatch --config config.toml serve cmtest \
  --bind <CENTRAL_LINUX_LAN_IP> \
  --port 8765
```

Öffnen Sie unter Windows `http://<CENTRAL_LINUX_LAN_IP>:8765/`. Ohne `--bind`
lauscht der Dienst nur auf `127.0.0.1`. Beenden Sie ihn nach der Prüfung mit
`Ctrl+C`.

`admin/admin` ist der vorhandene Standardwert. HTTP Basic Auth verschlüsselt die
Verbindung nicht. Dieser Modus ist für das vereinbarte vertrauenswürdige LAN
vorgesehen; setzen Sie bei Bedarf eigene Zugangsdaten oder verwenden Sie einen
vorhandenen HTTPS-Reverse-Proxy. Binden Sie den Dienst an eine private LAN-Adresse.
SSH-Schlüssel, IBM-Zugangsdaten, Konfigurationen und Inventardateien gehören
nicht in Git.

Zum Aktualisieren der zentralen Anwendung:

```bash
git pull --ff-only
. .venv/bin/activate
python -m pip install -e .
```

Bei Collector-Änderungen dessen Datei erneut auf den CM-Server übertragen.
`scripts/update_env.sh` kann die virtuelle Umgebung der zentralen Anwendung
reparieren; dieses Skript wird für die portable HTML-Datei nicht benötigt.

## Entwicklung und Prüfungen

Für die vollständigen Entwicklungstests werden Python 3.11+ mit `pytest` und
Node.js benötigt; CI verwendet Python 3.12 und Node.js 22. Node.js ist keine
Voraussetzung auf dem Windows-Arbeitsplatz oder dem CM-Server.

```bash
python3 -m pip install -e . pytest
python3 -m pytest -q
node --test tests/test_portable.js
python3 scripts/build_static_page.py
git diff --exit-code -- docs/IBM-Patchwatch.html
```

Nach beabsichtigten Änderungen an `web/` oder am Katalog die HTML-Datei neu
bauen und mit einchecken. Die letzte Prüfung kontrolliert anschließend die
reproduzierbare Ausgabe. Die Tests prüfen unter anderem Versionslinien,
fehlende oder widersprüchliche Angaben, Quellenalter, IM-Paketzuordnung,
Skripteinbettung und CSP-Hashes.

| Pfad | Aufgabe |
| --- | --- |
| `collectors/ibm_discovery.py` | Offline-Erfassung auf dem CM-Server, Inventarschema 1 |
| `data/ibm/catalog.json` | Bekannte IBM-Zielstände, Katalogschema 2 |
| `web/` | Deutsche Oberfläche, Vergleich und datierte IBM-Hinweise |
| `scripts/build_static_page.py` | Netzwerkfreier Builder für eine einzelne HTML-Datei |
| `docs/IBM-Patchwatch.html` | Generierte öffentliche HTML-Datei ohne Serverinventar |
| `scripts/update_ibm_catalog.py` und `src/ibm_patchwatch/providers/` | Abruf der IBM-Quellen |
| `src/ibm_patchwatch/` | Bestehende zentrale CLI-/LAN-Anwendung |

Die Anwendung installiert keine Patches. Die tatsächliche Erfassung auf den
IBM-Servern sowie authentifizierte Downloads und Voraussetzungen müssen in der
Zielumgebung geprüft werden. Ein vollständiger Sicherheits- oder
Kompatibilitätsaudit ist nicht Teil dieses Versionsvergleichs.
