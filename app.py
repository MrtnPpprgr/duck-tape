"""
Duck-Tape – Reparaturdatenbank für Platinen
=============================================
Lokal laufende Web-App (Flask + SQLite) mit Benutzerkonten/Berechtigungen,
die im Heim-/Firmennetzwerk von mehreren Geräten aus aufgerufen werden kann.

Start:  python app.py
Danach im Browser:  http://localhost:5000
Von anderen Geräten aus:  http://<IP-des-PCs>:5000

Beim allerersten Start wird automatisch ein Admin-Konto angelegt:
    Benutzername: admin
    Passwort:     admin123
Bitte direkt nach dem ersten Login das Passwort ändern (siehe "Mein Konto")!
"""

import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (Flask, g, render_template, request, redirect,
                    url_for, flash, send_from_directory, abort, session)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "reparaturen.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "duck-tape-secret-key-bitte-bei-bedarf-aendern"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB pro Upload

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------------------------
# Datenbank-Hilfsfunktionen
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            username                  TEXT COLLATE NOCASE UNIQUE NOT NULL,
            password_hash             TEXT NOT NULL,
            kann_anlegen              INTEGER NOT NULL DEFAULT 0,
            kann_loeschen             INTEGER NOT NULL DEFAULT 0,
            kann_reparatur_bearbeiten INTEGER NOT NULL DEFAULT 0,
            ist_admin                 INTEGER NOT NULL DEFAULT 0,
            erstellt_am               TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS platinen_typen (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT COLLATE NOCASE UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS platinen_versionen (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            typ_id  INTEGER NOT NULL,
            name    TEXT COLLATE NOCASE NOT NULL,
            UNIQUE (typ_id, name),
            FOREIGN KEY (typ_id) REFERENCES platinen_typen (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS platinen (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            seriennummer  TEXT COLLATE NOCASE UNIQUE NOT NULL,
            typ_id        INTEGER,
            version_id    INTEGER,
            erstellt_am   TEXT NOT NULL,
            erstellt_von  TEXT,
            FOREIGN KEY (typ_id) REFERENCES platinen_typen (id),
            FOREIGN KEY (version_id) REFERENCES platinen_versionen (id)
        );

        CREATE TABLE IF NOT EXISTS reparaturen (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            platine_id         INTEGER NOT NULL,
            datum              TEXT NOT NULL,
            fehlerbeschreibung TEXT,
            massnahme          TEXT,
            techniker          TEXT,
            kosten             TEXT,
            erstellt_am        TEXT NOT NULL,
            geaendert_am       TEXT,
            bearbeitet_von     TEXT,
            FOREIGN KEY (platine_id) REFERENCES platinen (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reparatur_fotos (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            reparatur_id   INTEGER NOT NULL,
            dateiname      TEXT NOT NULL,
            FOREIGN KEY (reparatur_id) REFERENCES reparaturen (id) ON DELETE CASCADE
        );
        """
    )
    db.commit()

    # Beim allerersten Start ein Admin-Konto anlegen
    anzahl_user = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if anzahl_user == 0:
        db.execute(
            """INSERT INTO users
               (username, password_hash, kann_anlegen, kann_loeschen,
                kann_reparatur_bearbeiten, ist_admin, erstellt_am)
               VALUES (?, ?, 1, 1, 1, 1, ?)""",
            ("admin", generate_password_hash("admin123"),
             datetime.now().isoformat(timespec="seconds")),
        )
        db.commit()
        print("\n*** Erstes Admin-Konto angelegt: Benutzername 'admin', Passwort 'admin123' ***")
        print("*** Bitte nach dem ersten Login unter 'Mein Konto' das Passwort aendern! ***\n")

    db.close()


def naechste_seriennummer(db):
    jahr = datetime.now().year
    row = db.execute(
        "SELECT COUNT(*) AS anzahl FROM platinen WHERE seriennummer LIKE ?",
        (f"PL-{jahr}-%",),
    ).fetchone()
    naechste_nr = row["anzahl"] + 1
    return f"PL-{jahr}-{naechste_nr:04d}"


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_or_create_typ(db, name):
    name = name.strip()
    row = db.execute("SELECT id FROM platinen_typen WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO platinen_typen (name) VALUES (?)", (name,))
    return cur.lastrowid


def get_or_create_version(db, typ_id, name):
    name = name.strip()
    row = db.execute(
        "SELECT id FROM platinen_versionen WHERE typ_id = ? AND name = ? COLLATE NOCASE",
        (typ_id, name),
    ).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO platinen_versionen (typ_id, name) VALUES (?, ?)", (typ_id, name))
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Login / Berechtigungen
# ---------------------------------------------------------------------------

@app.before_request
def lade_aktuellen_benutzer():
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        db = get_db()
        g.user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def permission_required(perm):
    """perm: 'kann_anlegen' | 'kann_loeschen' | 'kann_reparatur_bearbeiten' | 'ist_admin'"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login", next=request.path))
            if not (g.user["ist_admin"] or g.user[perm]):
                flash("Du hast keine Berechtigung für diese Aktion – nur Ansicht möglich.", "fehler")
                return redirect(request.referrer or url_for("index"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.context_processor
def inject_user():
    return {"aktueller_user": g.get("user")}


# ---------------------------------------------------------------------------
# Auth-Routen
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("index"))

    if request.method == "POST":
        db = get_db()
        username = request.form.get("username", "").strip()
        passwort = request.form.get("passwort", "")
        user = db.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], passwort):
            session.clear()
            session["user_id"] = user["id"]
            ziel = request.args.get("next") or url_for("index")
            return redirect(ziel)
        flash("Benutzername oder Passwort falsch.", "fehler")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/konto", methods=["GET", "POST"])
@login_required
def konto():
    if request.method == "POST":
        db = get_db()
        altes_pw = request.form.get("altes_passwort", "")
        neues_pw = request.form.get("neues_passwort", "")
        neues_pw2 = request.form.get("neues_passwort_wiederholen", "")

        if not check_password_hash(g.user["password_hash"], altes_pw):
            flash("Aktuelles Passwort ist falsch.", "fehler")
        elif len(neues_pw) < 4:
            flash("Neues Passwort muss mindestens 4 Zeichen haben.", "fehler")
        elif neues_pw != neues_pw2:
            flash("Die neuen Passwörter stimmen nicht überein.", "fehler")
        else:
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                       (generate_password_hash(neues_pw), g.user["id"]))
            db.commit()
            flash("Passwort wurde geändert.", "erfolg")
            return redirect(url_for("konto"))

    return render_template("konto.html")


# ---------------------------------------------------------------------------
# Benutzerverwaltung (nur Admin)
# ---------------------------------------------------------------------------

@app.route("/benutzer")
@permission_required("ist_admin")
def benutzer_liste():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY username COLLATE NOCASE").fetchall()
    return render_template("benutzer.html", users=users)


@app.route("/benutzer/neu", methods=["POST"])
@permission_required("ist_admin")
def benutzer_neu():
    db = get_db()
    username = request.form.get("username", "").strip()
    passwort = request.form.get("passwort", "").strip()

    if not username or not passwort:
        flash("Benutzername und Passwort werden benötigt.", "fehler")
        return redirect(url_for("benutzer_liste"))

    try:
        db.execute(
            """INSERT INTO users
               (username, password_hash, kann_anlegen, kann_loeschen,
                kann_reparatur_bearbeiten, ist_admin, erstellt_am)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (username, generate_password_hash(passwort),
             1 if request.form.get("kann_anlegen") else 0,
             1 if request.form.get("kann_loeschen") else 0,
             1 if request.form.get("kann_reparatur_bearbeiten") else 0,
             1 if request.form.get("ist_admin") else 0,
             datetime.now().isoformat(timespec="seconds")),
        )
        db.commit()
        flash(f"Konto '{username}' wurde angelegt.", "erfolg")
    except sqlite3.IntegrityError:
        flash(f"Benutzername '{username}' existiert bereits.", "fehler")

    return redirect(url_for("benutzer_liste"))


@app.route("/benutzer/<int:user_id>/aendern", methods=["POST"])
@permission_required("ist_admin")
def benutzer_aendern(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        abort(404)

    if user_id == g.user["id"] and not request.form.get("ist_admin"):
        flash("Du kannst dir nicht selbst die Admin-Rechte entziehen.", "fehler")
        return redirect(url_for("benutzer_liste"))

    db.execute(
        """UPDATE users SET kann_anlegen = ?, kann_loeschen = ?,
           kann_reparatur_bearbeiten = ?, ist_admin = ? WHERE id = ?""",
        (1 if request.form.get("kann_anlegen") else 0,
         1 if request.form.get("kann_loeschen") else 0,
         1 if request.form.get("kann_reparatur_bearbeiten") else 0,
         1 if request.form.get("ist_admin") else 0,
         user_id),
    )

    neues_pw = request.form.get("neues_passwort", "").strip()
    if neues_pw:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (generate_password_hash(neues_pw), user_id))

    db.commit()
    flash(f"Konto '{user['username']}' wurde aktualisiert.", "erfolg")
    return redirect(url_for("benutzer_liste"))


@app.route("/benutzer/<int:user_id>/loeschen", methods=["POST"])
@permission_required("ist_admin")
def benutzer_loeschen(user_id):
    if user_id == g.user["id"]:
        flash("Du kannst dein eigenes Konto nicht löschen.", "fehler")
        return redirect(url_for("benutzer_liste"))
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    flash("Konto wurde gelöscht.", "erfolg")
    return redirect(url_for("benutzer_liste"))


# ---------------------------------------------------------------------------
# Platinen-Übersicht mit Suche & Sortierung
# ---------------------------------------------------------------------------

SORTIERBARE_SPALTEN = {
    "seriennummer": "p.seriennummer COLLATE NOCASE",
    "typ": "typ_name COLLATE NOCASE",
    "version": "version_name COLLATE NOCASE",
    "anzahl": "anzahl_reparaturen",
    "letzte": "letzte_reparatur",
    "erstellt": "p.erstellt_am",
}


@app.route("/")
@login_required
def index():
    db = get_db()
    suche = request.args.get("q", "").strip()
    sort = request.args.get("sort", "erstellt")
    richtung = request.args.get("dir", "desc")
    if sort not in SORTIERBARE_SPALTEN:
        sort = "erstellt"
    if richtung not in ("asc", "desc"):
        richtung = "desc"

    basis_query = """
        SELECT p.*,
               t.name AS typ_name,
               v.name AS version_name,
               COUNT(r.id) AS anzahl_reparaturen,
               MAX(r.datum) AS letzte_reparatur
        FROM platinen p
        LEFT JOIN platinen_typen t ON t.id = p.typ_id
        LEFT JOIN platinen_versionen v ON v.id = p.version_id
        LEFT JOIN reparaturen r ON r.platine_id = p.id
    """
    params = []
    if suche:
        basis_query += """
            WHERE p.seriennummer LIKE ? OR t.name LIKE ? OR v.name LIKE ?
        """
        params += [f"%{suche}%", f"%{suche}%", f"%{suche}%"]

    basis_query += f" GROUP BY p.id ORDER BY {SORTIERBARE_SPALTEN[sort]} {richtung.upper()}"

    platinen = db.execute(basis_query, params).fetchall()
    vorschlag = naechste_seriennummer(db)

    typen = db.execute("SELECT * FROM platinen_typen ORDER BY name COLLATE NOCASE").fetchall()
    versionen = db.execute("SELECT * FROM platinen_versionen ORDER BY name COLLATE NOCASE").fetchall()

    return render_template(
        "index.html", platinen=platinen, suche=suche, vorschlag=vorschlag,
        typen=typen, versionen=versionen, sort=sort, richtung=richtung,
    )


@app.route("/platine/neu", methods=["POST"])
@permission_required("kann_anlegen")
def platine_neu():
    db = get_db()
    seriennummer = request.form.get("seriennummer", "").strip()
    if not seriennummer:
        seriennummer = naechste_seriennummer(db)

    typ_auswahl = request.form.get("typ_id", "")
    neuer_typ = request.form.get("neuer_typ", "").strip()
    version_auswahl = request.form.get("version_id", "")
    neue_version = request.form.get("neue_version", "").strip()

    typ_id = None
    version_id = None

    if typ_auswahl == "__neu__" and neuer_typ:
        typ_id = get_or_create_typ(db, neuer_typ)
    elif typ_auswahl.isdigit():
        typ_id = int(typ_auswahl)

    if typ_id is not None:
        if version_auswahl == "__neu__" and neue_version:
            version_id = get_or_create_version(db, typ_id, neue_version)
        elif version_auswahl.isdigit():
            version_id = int(version_auswahl)

    # Case-insensitive Duplikatsprüfung (zusätzlich zur DB-Constraint, für klare Fehlermeldung)
    vorhanden = db.execute(
        "SELECT id FROM platinen WHERE seriennummer = ? COLLATE NOCASE", (seriennummer,)
    ).fetchone()
    if vorhanden:
        flash(f"Eine Platine mit der Seriennummer '{seriennummer}' existiert bereits "
              f"(Groß-/Kleinschreibung wird ignoriert).", "fehler")
        return redirect(url_for("index"))

    cur = db.execute(
        "INSERT INTO platinen (seriennummer, typ_id, version_id, erstellt_am, erstellt_von) "
        "VALUES (?, ?, ?, ?, ?)",
        (seriennummer, typ_id, version_id, datetime.now().isoformat(timespec="seconds"),
         g.user["username"]),
    )
    db.commit()
    flash(f"Platine '{seriennummer}' wurde angelegt.", "erfolg")
    # Sofort zur Reparatur-Seite dieser neuen Platine weiterleiten
    return redirect(url_for("platine_detail", platine_id=cur.lastrowid))


@app.route("/typen/<int:typ_id>/versionen")
@login_required
def versionen_fuer_typ(typ_id):
    """Kleine JSON-Hilfsroute fürs kaskadierende Dropdown (Fallback, falls JS es braucht)."""
    db = get_db()
    versionen = db.execute(
        "SELECT id, name FROM platinen_versionen WHERE typ_id = ? ORDER BY name COLLATE NOCASE",
        (typ_id,),
    ).fetchall()
    return {"versionen": [{"id": v["id"], "name": v["name"]} for v in versionen]}


@app.route("/platine/<int:platine_id>")
@login_required
def platine_detail(platine_id):
    db = get_db()
    platine = db.execute(
        """SELECT p.*, t.name AS typ_name, v.name AS version_name
           FROM platinen p
           LEFT JOIN platinen_typen t ON t.id = p.typ_id
           LEFT JOIN platinen_versionen v ON v.id = p.version_id
           WHERE p.id = ?""",
        (platine_id,),
    ).fetchone()
    if platine is None:
        abort(404)

    reparaturen = db.execute(
        "SELECT * FROM reparaturen WHERE platine_id = ? ORDER BY datum DESC, id DESC",
        (platine_id,),
    ).fetchall()

    reparaturen_mit_fotos = []
    for rep in reparaturen:
        fotos = db.execute(
            "SELECT * FROM reparatur_fotos WHERE reparatur_id = ?", (rep["id"],)
        ).fetchall()
        reparaturen_mit_fotos.append({"rep": rep, "fotos": fotos})

    return render_template(
        "platine.html",
        platine=platine,
        reparaturen=reparaturen_mit_fotos,
        heute=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/platine/<int:platine_id>/reparatur", methods=["POST"])
@permission_required("kann_reparatur_bearbeiten")
def reparatur_neu(platine_id):
    db = get_db()
    platine = db.execute("SELECT * FROM platinen WHERE id = ?", (platine_id,)).fetchone()
    if platine is None:
        abort(404)

    datum = request.form.get("datum") or datetime.now().strftime("%Y-%m-%d")
    fehlerbeschreibung = request.form.get("fehlerbeschreibung", "").strip()
    massnahme = request.form.get("massnahme", "").strip()
    techniker = request.form.get("techniker", "").strip()
    kosten = request.form.get("kosten", "").strip()

    cur = db.execute(
        """INSERT INTO reparaturen
           (platine_id, datum, fehlerbeschreibung, massnahme, techniker, kosten, erstellt_am)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (platine_id, datum, fehlerbeschreibung, massnahme, techniker, kosten,
         datetime.now().isoformat(timespec="seconds")),
    )
    reparatur_id = cur.lastrowid

    dateien = request.files.getlist("fotos")
    for datei in dateien:
        if datei and datei.filename and allowed_file(datei.filename):
            sicherer_name = secure_filename(datei.filename)
            eindeutiger_name = f"{platine_id}_{reparatur_id}_{int(datetime.now().timestamp())}_{sicherer_name}"
            datei.save(os.path.join(app.config["UPLOAD_FOLDER"], eindeutiger_name))
            db.execute(
                "INSERT INTO reparatur_fotos (reparatur_id, dateiname) VALUES (?, ?)",
                (reparatur_id, eindeutiger_name),
            )

    db.commit()
    flash("Reparatur-Eintrag wurde hinzugefügt.", "erfolg")
    return redirect(url_for("platine_detail", platine_id=platine_id))


@app.route("/reparatur/<int:reparatur_id>/bearbeiten", methods=["GET", "POST"])
@permission_required("kann_reparatur_bearbeiten")
def reparatur_bearbeiten(reparatur_id):
    db = get_db()
    rep = db.execute("SELECT * FROM reparaturen WHERE id = ?", (reparatur_id,)).fetchone()
    if rep is None:
        abort(404)

    if request.method == "POST":
        datum = request.form.get("datum") or rep["datum"]
        fehlerbeschreibung = request.form.get("fehlerbeschreibung", "").strip()
        massnahme = request.form.get("massnahme", "").strip()
        techniker = request.form.get("techniker", "").strip()
        kosten = request.form.get("kosten", "").strip()

        db.execute(
            """UPDATE reparaturen SET datum = ?, fehlerbeschreibung = ?, massnahme = ?,
               techniker = ?, kosten = ?, geaendert_am = ?, bearbeitet_von = ?
               WHERE id = ?""",
            (datum, fehlerbeschreibung, massnahme, techniker, kosten,
             datetime.now().isoformat(timespec="seconds"), g.user["username"], reparatur_id),
        )

        dateien = request.files.getlist("fotos")
        for datei in dateien:
            if datei and datei.filename and allowed_file(datei.filename):
                sicherer_name = secure_filename(datei.filename)
                eindeutiger_name = f"{rep['platine_id']}_{reparatur_id}_{int(datetime.now().timestamp())}_{sicherer_name}"
                datei.save(os.path.join(app.config["UPLOAD_FOLDER"], eindeutiger_name))
                db.execute(
                    "INSERT INTO reparatur_fotos (reparatur_id, dateiname) VALUES (?, ?)",
                    (reparatur_id, eindeutiger_name),
                )

        loeschen_ids = request.form.getlist("foto_loeschen")
        for foto_id in loeschen_ids:
            foto = db.execute("SELECT * FROM reparatur_fotos WHERE id = ?", (foto_id,)).fetchone()
            if foto:
                pfad = os.path.join(app.config["UPLOAD_FOLDER"], foto["dateiname"])
                if os.path.exists(pfad):
                    os.remove(pfad)
                db.execute("DELETE FROM reparatur_fotos WHERE id = ?", (foto_id,))

        db.commit()
        flash("Reparatur-Eintrag wurde aktualisiert.", "erfolg")
        return redirect(url_for("platine_detail", platine_id=rep["platine_id"]))

    fotos = db.execute("SELECT * FROM reparatur_fotos WHERE reparatur_id = ?", (reparatur_id,)).fetchall()
    return render_template("reparatur_bearbeiten.html", rep=rep, fotos=fotos)


@app.route("/platine/<int:platine_id>/loeschen", methods=["POST"])
@permission_required("kann_loeschen")
def platine_loeschen(platine_id):
    db = get_db()
    platine = db.execute("SELECT * FROM platinen WHERE id = ?", (platine_id,)).fetchone()
    if platine is None:
        abort(404)
    db.execute("DELETE FROM platinen WHERE id = ?", (platine_id,))
    db.commit()
    flash(f"Platine '{platine['seriennummer']}' wurde gelöscht.", "erfolg")
    return redirect(url_for("index"))


@app.route("/uploads/<path:dateiname>")
@login_required
def uploaded_file(dateiname):
    return send_from_directory(app.config["UPLOAD_FOLDER"], dateiname)


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    print("\n" + "=" * 60)
    print(" Duck-Tape Reparaturdatenbank läuft!")
    print(" Auf diesem PC öffnen:      http://localhost:5000")
    print(" Von anderen Geräten aus:   http://<IP-DIESES-PCS>:5000")
    print(" (IP-Adresse herausfinden: siehe README.md)")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
