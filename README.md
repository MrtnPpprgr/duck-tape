# 🦆 Duck-Tape – Reparaturdatenbank für Platinen

Eine einfache, lokal laufende Web-App zum Erfassen von Reparaturen.
Läuft auf lokal auf einem PC und ist von anderen Geräten im selben Netzwerk aus über
den Browser erreichbar.



## Einmalige Einrichtung
Python herunterladen und requirements.txt installieren
 ```
 python install -r requirements.txt
 ```
```
python app.py
```
erster Benutzer beim starten einer leeren Datenbank ist immer 
Benutzer: "admin" Passwort:"admin"
```
Auf diesem PC öffnen:      http://localhost:5000
Von anderen Geräten aus:   http://<IP-DIESES-PCS>:5000
```



## Hinweise
Der Admin kann unter **"Benutzerverwaltung"** weitere Konten anlegen und pro
Konto einzeln folgende Rechte vergeben:
- **Reparaturen anlegen**
- **Reparaturen löschen**
- **Reparatur-Historie bearbeiten** (neue Einträge hinzufügen und bestehende ändern)
- **Admin** (zusätzlich: Benutzerverwaltung, hat automatisch alle Rechte)
Ein Konto **ohne** diese Häkchen kann sich zwar anmelden und alles ansehen,
aber nichts anlegen, ändern oder löschen (reine Ansichtsrechte).

Seriennummer Template kann in app.py in der funktion "def next_serial_number()" geändert werden.


## Daten & Backup

Alle Daten liegen in zwei Orten in diesem Ordner:
- `reparaturen.db` – die eigentliche Datenbank (SQLite-Datei)
- `static/uploads/` – die hochgeladenen Fotos/PDFs

Für ein Backup reicht es, den gesamten `duck-tape`-Ordner (oder zumindest
diese zwei Elemente) regelmäßig zu kopieren, z. B. auf ein Netzlaufwerk
oder in die Cloud.


## neue Felder
Wenn du ein neues Feld bei den Reparaturen ergänzen willst (z.B. "Priorität" oder "Dauer"), musst du an 6 Stellen etwas anpassen:

1. Datenbank-Schema – app.py, in init_db(), Tabelle repairs (~Zeile 104):

python
technician  TEXT,
parts       TEXT,
neues_feld   TEXT,   # <- neue Spalte hinzufügen

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

```
html
{% if repair['mein_feld'] %}
    <p><strong>Mein Feld:</strong> {{ repair['mein_feld'] }}</p>
{% endif %}
```