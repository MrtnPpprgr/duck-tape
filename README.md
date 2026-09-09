# 🦆 Duck-Tape – Repair Database for Circuit Boards

A simple, locally running web app for recording circuit boards and their complete repair history (faults, actions taken, technician, costs, photos).
It runs on your PC and can be accessed through a browser from other devices on the same network – nothing needs to be installed except Python.

## ⚠️ Note when updating from an older version

This version has a new database structure (user accounts, types/versions).
If you already have a `reparaturen.db` from an older version of this app, delete this file once before starting the new version so that the new tables can be created correctly (existing photos in `static/uploads/` are not affected, but if the old database is deleted, they will no longer be associated with a circuit board).

## 1. Requirement: Install Python

If not already installed: install Python 3.10 or newer from
https://www.python.org/downloads/.
**Important (Windows):** during installation, check the box "Add python.exe to PATH".

To check whether Python is installed, open a terminal / command prompt:

```
python --version
```

(On some systems, the command is `python3` instead of `python`.)

## 2. One-time setup

Open a terminal in the `duck-tape` folder (this folder) and run:

```
python -m venv venv
```

Then activate the virtual environment:

- **Windows:** `venv\Scripts\activate`
- **Mac/Linux:** `source venv/bin/activate`

Then install the required packages:

```
pip install -r requirements.txt
```

## 3. Start the app

```
python app.py
```

The terminal will display, among other things:

```
Open on this PC:      http://localhost:5000
From other devices:   http://<IP-OF-THIS-PC>:5000
```

On the PC itself, simply open `http://localhost:5000` in your browser.

## 4. Access the app from other devices on the network

To allow colleagues/other PCs or mobile phones on the same Wi-Fi/LAN to access the database, you need the local IP address of the PC running the app:

- **Windows:** Command Prompt → `ipconfig` → value next to "IPv4 Address"
  (e.g. `192.168.1.42`)
- **Mac:** Terminal → `ipconfig getifaddr en0` (for Wi-Fi) or System Settings → Network
- **Linux:** Terminal → `hostname -I`

Other devices can then open the following address in their browser:

```
http://192.168.1.42:5000
```

(Replace the example IP address with the actual IP address of your PC.)

**Hinweise:**
- Der PC, auf dem `python app.py` läuft, muss dafür eingeschaltet und im
  gleichen Netzwerk sein (WLAN oder LAN, kein separates Gäste-WLAN).
- Falls andere Geräte die Seite nicht erreichen, prüfe die Windows-Firewall –
  ggf. muss Python/Port 5000 einmalig freigegeben werden (Meldung dazu
  erscheint meist automatisch beim ersten Start).
- Damit die App dauerhaft erreichbar ist, muss das Terminal-Fenster mit
  `python app.py` offen bleiben (oder die App z. B. per Task-Planer/Autostart
  automatisch starten lassen – bei Bedarf kann ich das ergänzen).

## 5. Login & User Accounts

The app is now protected by a login. The first time it is started, an admin account is automatically created:

```
Username: admin
Password:     admin123
```

**Please change the password immediately after the first login under "My Account"!**

The admin can create additional accounts under **"User Management"** and assign the following permissions individually to each account:

- **Create circuit boards**
- **Delete circuit boards**
- **Edit repair history** (add new entries and modify existing ones)
- **Admin** (in addition: user management, automatically has all permissions)

An account **without** these permissions can still log in and view everything, but cannot create, modify, or delete anything (view-only access).

## 6. Features

- **Create a new circuit board** – with an automatically assigned serial number
  (format `PL-YEAR-SEQUENCE_NUMBER`, e.g. `PL-2026-0007`) or a custom serial number. The check for existing serial numbers is case-insensitive (`abc-001` and `ABC-001` are considered the same number).
  **After creation**, the detail/repair page of the new circuit board opens immediately.
- **Type & Version via dropdown** – when creating a circuit board, first select the circuit board type and then the appropriate version from a dropdown list (the version list automatically adjusts to the selected type). New entries can be added directly during creation via "+ New Type..." or "+ New Version...".
- **Overview, Search & Sorting** – all circuit boards are displayed with the number of previous repairs; search by serial number, type, or version; each column heading is clickable and sorts the table in ascending/descending order.
- **Repair History per Circuit Board** – each repair is stored as a new history entry (nothing is automatically overwritten), including:
  - Date
  - Fault description
  - Repair/action performed
  - Technician/Editor
  - Costs/Replacement parts
  - Photos/Attachments (multiple images or PDFs per entry)
- **Edit Repair Entries** – existing history entries can be corrected afterwards (including adding/removing photos); the date and person who last modified the entry are displayed.
- Wird eine Platine mehrfach repariert, siehst du auf der Übersichtsseite
  sofort "2× repariert", "3× repariert" usw., und auf der Detailseite die
  komplette Chronik.

## 7. Data & Backup

All data is stored in two locations within this folder:
- `reparaturen.db` – the actual database (SQLite file)
- `static/uploads/` – the uploaded photos/PDFs

For a backup, simply copy the entire `duck-tape` folder (or at least these two items) regularly, e.g. to a network drive or the cloud.

## 8. Starting the app again in the future

After the initial setup, you only need to run:

```
cd duck-tape
venv\Scripts\activate        (Windows)   bzw.   source venv/bin/activate   (Mac/Linux)
python app.py
```


## Add fields to Database

If you want to add a new field to the repairs (e.g. "Priority" or "Duration"), you need to make changes in 6 places:

1. Database schema – `app.py`, in `init_db()`, `repairs` table (~line 104):

python
technician  TEXT,
parts       TEXT,
mein_feld   TEXT,   # <- add new column

⚠️ Important: With an existing `reparaturen.db`, SQLite will not automatically create the new column. You must either delete the file (data will be lost) or run the following command once:

2. Save a new repair – `app.py`, route `create_repair` (~line 526):

python
mein_feld = request.form.get("mein_feld", "").strip()

and add it to the `INSERT INTO repairs (...)` statement and the values tuple.

3. Edit a repair – `app.py`, route `edit_repair` (~line 566):
Do the same again: `request.form.get(...)`, plus the `UPDATE repairs SET ...` statement and the values tuple.

4. Form "New Repair" – `templates/board.html`:

html
<label>My Field:
    <input type="text" name="mein_feld">
</label>

5. Form "Edit Repair" – `templates/edit_repair.html`:

html
<label>My Field:
    <input type="text" name="mein_feld" value="{{ repair['mein_feld'] or '' }}">
</label>

6. Display in the history – `templates/board.html`, in the timeline block:

html
{% if repair['mein_feld'] %}
    <p><strong>My Field::</strong> {{ repair['mein_feld'] }}</p>
{% endif %}