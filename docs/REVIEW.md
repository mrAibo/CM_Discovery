# Prüfung von Patchwatch und Bedienung

Stand: 14.10.2026. Prüfumfang: portable Oberfläche, JSON-Import,
Versionsvergleich, Collector-Fehlerstatus, öffentliche Ausgabe und CI.

## Behobene Fehler

| Problem | Korrektur |
| --- | --- |
| Alter Katalog verdeckte einen Collector-Fehler | Erfassungsfehler haben Vorrang im Vergleich; auch ohne Produkteintrag erscheinen Status und geprüfter Pfad. |
| Db2-Ausgabe enthielt eine plausible Version trotz Fehlercode | Der Fehlerstatus bleibt erhalten; eine erfolgreiche Texterkennung setzt ihn nicht auf `ok`. |
| WAS bzw. ICN/ICCSAP lieferten ein unbekanntes Ausgabeformat | Fehlende erkannte Produktversionen werden als `parse_error` gekennzeichnet. |
| Mit ICN geliefertes Daeja konnte bei älterer Basis als separates Update erscheinen | Die Zuordnung zu ICN wird vor dem Versionsvergleich geprüft. |
| Katalogimport prüfte verschachtelte iFix-Daten unzureichend | Struktur und Feldtypen werden geprüft; ein fehlerhafter Import wird vollständig abgelehnt. |
| Mehrere Dateiimporte konnten in falscher Reihenfolge enden | Nur die jüngste Auswahl wird übernommen; ganze Datei-Batches werden atomar validiert. |
| Fehlgeschlagener Render konnte bereits übernommene Daten zurücklassen | Der alte Zustand wird wiederhergestellt; die Tabelle wird erst als fertiges DOM-Fragment ersetzt. |
| Quellenwarnung bot auch bei ausschließlich alten Hinweisen einen neuen Katalog als Lösung an | Warnungen nennen passend die neue HTML-Datei oder einen neuen Serverscan; der Katalogknopf erscheint nur bei veralteten Katalogeinträgen. |
| Zielpaket stand hinter der bisherigen Basis-Auswahl | Ziel-Download zuerst, äquivalente IBM-URLs werden dedupliziert. |

## Bedienung und Optimierung

- Kurzer Einstieg, sichtbarer Inventar-/Katalogimport und Drag-and-drop beider JSON-Dateien.
- Gesamtzahlen für Updates, Prüfungen und übereinstimmenden Stand; direkt als Filter nutzbar.
- Suche nach Produkt, Version oder Installationspfad, Leerzustand und Filter-Reset.
- Handlungsbedarf zuerst, Details und iFixes aufklappbar, mobile Karten und Druckansicht.
- Produktgruppierung über eine Map statt wiederholter kompletter Produktsuchen; getrennte Installationen bleiben erhalten.
- Keine Framework-, Server- oder Browser-Netzwerk-Abhängigkeit in der Ausgabe. Playwright ist ausschließlich eine Entwicklungsabhängigkeit.

## Verbleibende Grenzen

Einige Provider lesen weiterhin eine Readme für einen fest bekannten Release-Stand.
Ein erfolgreicher neuer Abruf belegt die Lesbarkeit der Seite, nicht die Entdeckung
aller nachfolgenden Releases. Die Erweiterung um geprüfte IBM-Release-Indizes ist
ein sinnvoller nächster funktionaler Schritt. Fix-Central-Berechtigungen und
Paketvoraussetzungen bleiben getrennt von der Anzeige.

Datierte Hinweise und iFix-Referenzen werden nicht automatisch fachlich neu geprüft.
Die Oberfläche kennzeichnet ihr Alter. Ein neues Katalogdatum erneuert diese Prüfung nicht.

Collector-Pfade sind weiterhin umgebungsspezifisch. Für eine spätere Verallgemeinerung
sind konfigurierbare Pfade geeigneter als weitere fest eingebaute Servernamen.

Die Installationsrolle hat synthetische Ansible-Tests. Eine Abnahme mit den konkreten
IBM-Medien, Response-Dateien, Dienstplänen und Wiederherstellungsverfahren auf dem
realen Testserver wurde in dieser Prüfung nicht durchgeführt. Daraus wird keine
Produktionsfreigabe abgeleitet.

## Validierung

Python- und JavaScript-Tests prüfen Fehlerpriorität, Parserstatus, JSON-Strukturen,
Datei-Batches, Filter, Download-Reihenfolge und Reproduzierbarkeit der Ausgabe.
Chromium-Tests prüfen echte Dateiimporte, Drag-and-drop, konkurrierende Ladevorgänge,
Erhalt alter Daten, sichere Textdarstellung, Druckansicht und mobile Breite.
Die Browser-Tests laufen zusätzlich in GitHub Actions.
