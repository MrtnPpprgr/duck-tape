# 🦆 Duck-Tape – Reparaturdatenbank für Platinen

Eine einfache, lokal laufende Web-App zum Erfassen von Platinen und ihrer
kompletten Reparatur-Historie (Fehler, Maßnahme, Techniker, Kosten, Fotos).
Läuft auf deinem PC und ist von anderen Geräten im selben Netzwerk aus über
den Browser erreichbar – es muss nichts extra installiert werden außer Python.

## 1. Voraussetzung: Python installieren

Falls noch nicht vorhanden: Python 3.10 oder neuer von
https://www.python.org/downloads/ installieren.
**Wichtig (Windows):** beim Installer den Haken bei "Add python.exe to PATH" setzen.

Prüfen, ob Python installiert ist (Terminal / Eingabeaufforderung öffnen):

```
python --version
```

(Auf manchen Systemen heißt der Befehl `python3` statt `python`.)

## 2. Einmalige Einrichtung

Im Ordner `duck-tape` (dieser Ordner) ein Terminal öffnen und ausführen:

```
python -m venv venv
```

Danach die virtuelle Umgebung aktivieren:

- **Windows:** `venv\Scripts\activate`
- **Mac/Linux:** `source venv/bin/activate`

Dann die benötigten Pakete installieren:

```
pip install -r requirements.txt
```

## 3. App starten

```
python app.py
```

Im Terminal erscheint u.a.:

```
Auf diesem PC öffnen:      http://localhost:5000
Von anderen Geräten aus:   http://<IP-DIESES-PCS>:5000
```

Auf dem PC selbst einfach `http://localhost:5000` im Browser öffnen.

## 4. Von anderen Geräten im Netzwerk aus zugreifen

Damit Kollegen/andere PCs oder Handys im selben WLAN/LAN die Datenbank öffnen
können, brauchst du die lokale IP-Adresse des PCs, auf dem die App läuft:

- **Windows:** Eingabeaufforderung → `ipconfig` → Wert bei "IPv4-Adresse"
  (z. B. `192.168.1.42`)
- **Mac:** Terminal → `ipconfig getifaddr en0` (bei WLAN) oder Systemeinstellungen → Netzwerk
- **Linux:** Terminal → `hostname -I`

Andere Geräte rufen dann im Browser auf:

```
http://192.168.1.42:5000
```

(Statt der Beispiel-IP die tatsächliche IP-Adresse deines PCs einsetzen.)

**Hinweise:**
- Der PC, auf dem `python app.py` läuft, muss dafür eingeschaltet und im
  gleichen Netzwerk sein (WLAN oder LAN, kein separates Gäste-WLAN).
- Falls andere Geräte die Seite nicht erreichen, prüfe die Windows-Firewall –
  ggf. muss Python/Port 5000 einmalig freigegeben werden (Meldung dazu
  erscheint meist automatisch beim ersten Start).
- Damit die App dauerhaft erreichbar ist, muss das Terminal-Fenster mit
  `python app.py` offen bleiben (oder die App z. B. per Task-Planer/Autostart
  automatisch starten lassen – bei Bedarf kann ich das ergänzen).

## 5. Funktionen

- **Neue Platine anlegen** – mit automatisch vergebener Seriennummer
  (Format `PL-JAHR-LAUFENDENUMMER`, z. B. `PL-2026-0007`) oder eigener
  Seriennummer.
- **Übersicht & Suche** – alle Platinen mit Anzahl bisheriger Reparaturen;
  Suche nach Seriennummer oder Bezeichnung.
- **Reparatur-Historie je Platine** – jede Reparatur wird als neuer
  Historien-Eintrag gespeichert (nichts wird überschrieben), mit:
  - Datum
  - Fehlerbeschreibung
  - durchgeführte Reparatur/Maßnahme
  - Techniker/Bearbeiter
  - Kosten/Ersatzteile
  - Fotos/Anhänge (mehrere Bilder oder PDFs pro Eintrag)
- Wird eine Platine mehrfach repariert, siehst du auf der Übersichtsseite
  sofort "2× repariert", "3× repariert" usw., und auf der Detailseite die
  komplette Chronik.

## 6. Daten & Backup

Alle Daten liegen in zwei Orten in diesem Ordner:
- `reparaturen.db` – die eigentliche Datenbank (SQLite-Datei)
- `static/uploads/` – die hochgeladenen Fotos/PDFs

Für ein Backup reicht es, den gesamten `duck-tape`-Ordner (oder zumindest
diese zwei Elemente) regelmäßig zu kopieren, z. B. auf ein Netzlaufwerk
oder in die Cloud.

## 7. App künftig wieder starten

Nach der Ersteinrichtung reicht künftig:

```
cd duck-tape
venv\Scripts\activate        (Windows)   bzw.   source venv/bin/activate   (Mac/Linux)
python app.py
```
