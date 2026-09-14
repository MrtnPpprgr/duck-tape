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

  **Etikett-Vorlagen (nur Admin gestaltet, alle Berechtigten drucken):**
  Ganz oben auf der Etiketten-Seite kann ein **Admin** unter "Etikett-Design"
  das komplette Aussehen eines Etiketts gestalten — Größe, ob QR-Code und/
  oder Seriennummer erscheinen und wo genau (per Drag & Drop im
  Vorschaukästchen oder als mm-Koordinaten), beliebig viele zusätzliche
  Textzeilen (z. B. Firmenname, Warnhinweis), die auf jedem gedruckten
  Etikett identisch bleiben, **sowie die Seiteneinstellungen** (Abstand
  zwischen den Etiketten, Seitenränder des DIN-A4-Bogens). Das Ergebnis
  wird unter einem frei wählbaren Namen als **Vorlage** gespeichert;
  bestehende Vorlagen lassen sich über "Vorlage laden / bearbeiten" wieder
  öffnen, ändern (erneutes Speichern unter demselben Namen aktualisiert
  sie) oder löschen. Dieser Design-Bereich ist ausschließlich für
  Admin-Konten sichtbar.

  Alle anderen Nutzer mit "Platinen anlegen"-Recht sehen nur den
  darunterliegenden **Druck-Bereich**: dort wird eine der gespeicherten
  Vorlagen aus einem Dropdown ausgewählt (inkl. Vorschau) — Größe,
  Abstände und Seitenränder werden dabei automatisch aus der Vorlage
  übernommen und müssen nicht erneut eingegeben werden. Zusätzlich werden
  nur noch die je Druckauftrag unterschiedlichen Angaben gemacht:
  Start-Seriennummer, Anzahl und Startposition auf dem Bogen. Ohne
  mindestens eine gespeicherte Vorlage kann nicht gedruckt werden — es
  erscheint dann ein Hinweis, einen Admin um das Anlegen einer Vorlage zu
  bitten.



## 7. Daten & Backup

Alle Daten liegen in zwei Orten in diesem Ordner:
- `reparaturen.db` – die eigentliche Datenbank (SQLite-Datei)
- `static/uploads/` – die hochgeladenen Fotos/PDFs

Für ein Backup reicht es, den gesamten `duck-tape`-Ordner (oder zumindest
diese zwei Elemente) regelmäßig zu kopieren, z. B. auf ein Netzlaufwerk
oder in die Cloud.

## 8. HTTPS aktivieren (für Kamera-QR-Scanner von anderen Geräten)

Browser erlauben Kamerazugriff (für den QR-Code-Scanner im Suchfeld) aus
Sicherheitsgründen nur über **HTTPS** oder **`http://localhost`** — nicht
über eine normale `http://`-Netzwerk-IP. Auf dem PC selbst funktioniert der
Scanner also auch ohne diesen Schritt (über `localhost`); für andere Geräte
im Netzwerk (z. B. Handys) ist HTTPS nötig.

**Einmalige Einrichtung:**

```
python generate_cert.py
```

Das erzeugt automatisch `cert.pem` und `key.pem` in diesem Ordner, gültig
für `localhost` sowie die aktuell erkannte(n) lokale(n) Netzwerk-IP(s)
dieses PCs. Startest du die App danach ganz normal mit `python app.py`,
läuft sie automatisch über **HTTPS** (das erkennt die App selbst daran, ob
`cert.pem`/`key.pem` vorhanden sind — ohne diese Dateien läuft alles wie
gehabt über HTTP).

**Aufruf danach:**
```
https://localhost:5000              (auf diesem PC)
https://<IP-DIESES-PCS>:5000        (von anderen Geräten im Netzwerk)
```

**Browser-Warnung bestätigen:** Da es sich um ein **selbstsigniertes**
Zertifikat handelt (nicht von einer offiziellen Stelle ausgestellt), zeigt
jeder Browser beim ersten Aufruf eine Warnung wie "Nicht sicher" oder
"Verbindung ist nicht privat". Das ist normal — auf **"Erweitert"** bzw.
**"Details"** und dann **"Trotzdem fortfahren" / "Weiter zu ... (unsicher)"**
klicken. Das muss auf **jedem Gerät einmalig** gemacht werden, das
zugreift; danach funktioniert alles inklusive Kamera ohne weitere Hinweise.

**Wichtig — IP-Adresse ändert sich:** Bekommt der Server-PC durch einen
Neustart oder Router-Neuvergabe eine neue lokale IP-Adresse, passt das
Zertifikat nicht mehr zur neuen Adresse (Browser zeigen dann eine andere
Fehlermeldung, z. B. zur falschen Adresse). In dem Fall einfach erneut
`python generate_cert.py` ausführen — es erkennt die neue IP automatisch
und erstellt ein passendes Zertifikat. Für dauerhaft stabile Verhältnisse
empfiehlt es sich, dem Server-PC im Router eine **feste lokale IP-Adresse**
zuzuweisen.

## 9. App künftig wieder starten

Nach der Ersteinrichtung reicht künftig:

```
cd duck-tape
venv\Scripts\activate        (Windows)   bzw.   source venv/bin/activate   (Mac/Linux)
python app.py
```
