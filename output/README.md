# IBM Patchwatch – fertige Dateien

Dieser Ordner enthält das vollständige portable Paket:

- `IBM-Patchwatch.html`: im Windows-Browser öffnen.
- `catalog.json`: dieselben Katalogdaten, die in der HTML-Datei eingebettet sind.
- `verified-notes.json`: dieselben datierten Hinweise wie in der HTML-Datei.
- `ibm_discovery.py`: auf den IBM-Server kopieren und dort das Inventar erzeugen:

```bash
python3 ibm_discovery.py --json > inventory.json
```

`inventory.json` vom IBM-Server in den lokalen Arbeitsordner übertragen und in
HTML über **Inventar öffnen** laden. Das öffentliche Paket enthält keine
Serverinventare. Der Collector benötigt Linux und Python 3.6+; der Browservergleich
benötigt keine Installation auf Windows. IBM-Pakete werden manuell heruntergeladen.

**Aktualisierung:** Den ganzen Ordner erneut herunterladen. Zum Import eines
neueren Katalogs in eine bereits geöffnete Seite **Katalog aktualisieren** verwenden.
Für neue Hinweise ebenfalls die neue HTML-Datei öffnen.

Die JSON-Kopien werden beim Build übernommen; Änderungen an den Quelldateien
werden erst durch einen erneuten Build in diesen Ordner übertragen. Die Hinweise
behalten ihr fachliches Prüfdatum unabhängig vom Katalogabruf.
