# IBM Patchwatch – fertige Dateien

So starten Sie IBM Patchwatch in fünf Schritten (ohne Installation, ohne Internet-Upload):

1. Auf GitHub **Code → Download ZIP** wählen (oder `git clone`).
2. ZIP entpacken; der Ordner `output/` enthält alles Nötige.
3. `IBM-Patchwatch.html` per Doppelklick im Browser öffnen.
4. `ibm_discovery.py` auf den IBM-Server kopieren und dort ausführen:
   `python3 ibm_discovery.py --json > inventory.json`
   (ohne Kopieren: `ssh SERVER 'python3 - --json' < ibm_discovery.py > inventory-SERVER.json`).
5. `inventory.json` in der Seite über **Inventar öffnen** laden oder auf die Seite ziehen.

Weitere Dateien: `catalog.json` und `verified-notes.json` sind dieselben Daten, die in
der HTML-Datei eingebettet sind. Das öffentliche Paket enthält keine
Serverinventare. Der Collector benötigt Linux und Python 3.6+; er liest nur und
sollte nicht als root laufen. Mit `--path KEY=PFAD` lassen sich abweichende
Installationspfade angeben, mit `--output DATEI` wird in eine Datei geschrieben.

**Aktualisierung:** Den ganzen Ordner erneut herunterladen. Zum Import eines
neueren Katalogs in eine bereits geöffnete Seite **Katalog aktualisieren** verwenden.
Eine heruntergeladene HTML-Datei aktualisiert sich nicht selbst.
