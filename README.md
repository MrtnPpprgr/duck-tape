# 🦆 Duck-Tape – Reparaturdatenbank für Platinen

Eine einfache, lokal laufende Web-App zum Erfassen von Platinen und ihrer
kompletten Reparatur-Historie (Fehler, Maßnahme, Techniker, Kosten, Fotos).
Läuft auf deinem PC und ist von anderen Geräten im selben Netzwerk aus über
den Browser erreichbar – es muss nichts extra installiert werden außer Python.

## ⚠️ Hinweis bei einem Update von einer älteren Version

Diese Version hat eine neue Datenbankstruktur (Benutzerkonten, Typen/Versionen).
Falls du schon eine `reparaturen.db` von einer älteren Version dieser App hast,
lösche diese Datei einmalig, bevor du die neue Version startest, damit die
neuen Tabellen sauber angelegt werden (bereits erfasste Fotos in
`static/uploads/` bleiben unabhängig davon erhalten, sind dann aber keiner
Platine mehr zugeordnet, falls die alte Datenbank gelöscht wird).

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

## 5. Anmeldung & Benutzerkonten

Die App ist jetzt durch einen Login geschützt. Beim allerersten Start wird
automatisch ein Admin-Konto angelegt:

```
Benutzername: admin
Passwort:     admin123
```

**Bitte direkt nach dem ersten Login unter "Mein Konto" das Passwort ändern!**

Der Admin kann unter **"Benutzerverwaltung"** weitere Konten anlegen und pro
Konto einzeln folgende Rechte vergeben:

- **Platinen anlegen**
- **Platinen löschen**
- **Reparatur-Historie bearbeiten** (neue Einträge hinzufügen und bestehende ändern)
- **Admin** (zusätzlich: Benutzerverwaltung, hat automatisch alle Rechte)

Ein Konto **ohne** diese Häkchen kann sich zwar anmelden und alles ansehen,
aber nichts anlegen, ändern oder löschen (reine Ansichtsrechte).

## 6. Funktionen

- **Neue Platine anlegen** – mit automatisch vergebener Seriennummer
  (Format `PL-JAHR-LAUFENDENUMMER`, z. B. `PL-2026-0007`) oder eigener
  Seriennummer. Die Prüfung auf bereits vorhandene Seriennummern ignoriert
  Groß-/Kleinschreibung (`abc-001` und `ABC-001` gelten als dieselbe Nummer).
  **Nach dem Anlegen** öffnet sich sofort die Detail-/Reparaturseite der
  neuen Platine.
- **Typ & Version per Dropdown** – beim Anlegen einer Platine wählt man
  zuerst den Platinen-Typ und danach die passende Version aus einer
  Dropdown-Liste (die Versionsliste passt sich automatisch an den gewählten
  Typ an). Über "+ Neuer Typ..." bzw. "+ Neue Version..." lassen sich neue
  Einträge direkt beim Anlegen ergänzen.
- **Übersicht, Suche & Sortierung** – alle Platinen mit Anzahl bisheriger
  Reparaturen; Suche nach Seriennummer, Typ oder Version; jede Spaltenüber-
  schrift ist klickbar und sortiert die Tabelle auf-/absteigend.
- **Reparatur-Historie je Platine** – jede Reparatur wird als neuer
  Historien-Eintrag gespeichert (nichts wird automatisch überschrieben), mit:
  - Datum
  - Fehlerbeschreibung
  - durchgeführte Reparatur/Maßnahme
  - Techniker/Bearbeiter
  - Kosten/Ersatzteile
  - Fotos/Anhänge (mehrere Bilder oder PDFs pro Eintrag)
- **Reparatur-Einträge bearbeiten** – bestehende Historien-Einträge können
  nachträglich korrigiert werden (inkl. Fotos hinzufügen/entfernen);
  sichtbar ist dabei, wann und von wem zuletzt geändert wurde.
- Wird eine Platine mehrfach repariert, siehst du auf der Übersichtsseite
  sofort "2× repariert", "3× repariert" usw., und auf der Detailseite die
  komplette Chronik.
- **QR-Code je Platine** – auf der Detailseite jeder Platine wird ein
  QR-Code angezeigt, der auf Klick als PNG heruntergeladen werden kann
  (enthält die Seriennummer).
- **Etiketten drucken (DIN A4)** – über "Etiketten drucken" in der
  Navigation lässt sich ein PDF-Bogen mit QR-Code-Etiketten erzeugen:
  - Etikettengröße (Breite/Höhe)
  - Abstand zwischen den Etiketten (horizontal/vertikal)
  - Seitenränder (oben/unten/links/rechts)
  - Anzahl der zu druckenden Etiketten
  - Startposition auf dem Bogen (praktisch für teilweise benutzte
    Etikettenbögen — Position 1 = oben links, dann zeilenweise weiter)

  Die Seriennummern werden ab einer angegebenen Start-Nummer hochgezählt;
  bereits vergebene Nummern werden automatisch übersprungen und durch die
  nächsthöhere freie Nummer ersetzt. Die erzeugten Nummern werden dabei
  **nicht automatisch** in der Datenbank angelegt — sie sind nur so lange
  "reserviert", bis die jeweilige Platine später mit genau dieser Nummer
  angelegt wird.

## 7. Daten & Backup

Alle Daten liegen in zwei Orten in diesem Ordner:
- `reparaturen.db` – die eigentliche Datenbank (SQLite-Datei)
- `static/uploads/` – die hochgeladenen Fotos/PDFs

Für ein Backup reicht es, den gesamten `duck-tape`-Ordner (oder zumindest
diese zwei Elemente) regelmäßig zu kopieren, z. B. auf ein Netzlaufwerk
oder in die Cloud.

## 8. App künftig wieder starten

Nach der Ersteinrichtung reicht künftig:

```
cd duck-tape
venv\Scripts\activate        (Windows)   bzw.   source venv/bin/activate   (Mac/Linux)
python app.py
```


## Add fields to Database

Wenn du ein neues Feld bei den Reparaturen ergänzen willst (z.B. "Priorität" oder "Dauer"), musst du an 6 Stellen etwas anpassen:

1. Datenbank-Schema – app.py, in init_db(), Tabelle repairs (~Zeile 104):

python
technician  TEXT,
parts       TEXT,
mein_feld   TEXT,   # <- neue Spalte hinzufügen

⚠️ Wichtig: Bei einer bestehenden reparaturen.db legt SQLite die neue Spalte nicht automatisch an. Du musst entweder die Datei löschen (Daten weg) oder einmalig ALTER TABLE repairs ADD COLUMN mein_feld TEXT; ausführen.

2. Neue Reparatur speichern – app.py, Route create_repair (~Zeile 526):

python
mein_feld = request.form.get("mein_feld", "").strip()

und in den INSERT INTO repairs (...) sowie im Werte-Tupel ergänzen.

3. Reparatur bearbeiten – app.py, Route edit_repair (~Zeile 566):
Gleiches nochmal: request.form.get(...), plus im UPDATE repairs SET ... und im Werte-Tupel.

4. Formular „Neue Reparatur" – templates/board.html:

html
<label>Mein Feld
    <input type="text" name="mein_feld">
</label>

5. Formular „Reparatur bearbeiten" – templates/edit_repair.html:

html
<label>Mein Feld
    <input type="text" name="mein_feld" value="{{ repair['mein_feld'] or '' }}">
</label>

6. Anzeige in der Historie – templates/board.html, im Timeline-Block:

html
{% if repair['mein_feld'] %}
    <p><strong>Mein Feld:</strong> {{ repair['mein_feld'] }}</p>
{% endif %}