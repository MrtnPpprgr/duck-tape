"""
Duck-Tape - Repair database for PCBs (Platinen)
=================================================
A locally hosted web app (Flask + SQLite) with user accounts/permissions,
reachable from other devices on the same home/office network.

Start:  python app.py
Then open in a browser:  http://localhost:5000
From other devices:      http://<PC-IP>:5000

On first run a default admin account is created automatically:
    Username: admin
    Password: admin
Please change the password right after the first login (see "Mein Konto")!
"""

import os
import re
import json
import sqlite3
import qrcode
from io import BytesIO
from datetime import datetime
from functools import wraps
from io import BytesIO

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas

from flask import (Flask, g, render_template, request, redirect,
                    url_for, flash, send_from_directory, send_file, abort, session)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "repairs.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "duck-tape-secret-key-please-change-if-needed"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB per upload

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------------------------
# Database helpers
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
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            username           TEXT COLLATE NOCASE UNIQUE NOT NULL,
            password_hash      TEXT NOT NULL,
            can_create         INTEGER NOT NULL DEFAULT 0,
            can_delete         INTEGER NOT NULL DEFAULT 0,
            can_edit_repairs   INTEGER NOT NULL DEFAULT 0,
            is_admin           INTEGER NOT NULL DEFAULT 0,
            created_at         TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS board_types (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT COLLATE NOCASE UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS board_versions (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            type_id  INTEGER NOT NULL,
            name     TEXT COLLATE NOCASE NOT NULL,
            UNIQUE (type_id, name),
            FOREIGN KEY (type_id) REFERENCES board_types (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS boards (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number   TEXT COLLATE NOCASE UNIQUE NOT NULL,
            type_id         INTEGER,
            version_id      INTEGER,
            created_at      TEXT NOT NULL,
            created_by      TEXT,
            FOREIGN KEY (type_id) REFERENCES board_types (id),
            FOREIGN KEY (version_id) REFERENCES board_versions (id)
        );

        CREATE TABLE IF NOT EXISTS repairs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            board_id            INTEGER NOT NULL,
            date                TEXT NOT NULL,
            issue_description   TEXT,
            action_taken        TEXT,
            technician          TEXT,
            parts               TEXT,
            ticket              TEXT,
            customer            TEXT,
            created_at          TEXT NOT NULL,
            updated_at          TEXT,
            updated_by          TEXT,
            FOREIGN KEY (board_id) REFERENCES boards (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS repair_attachments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_id   INTEGER NOT NULL,
            filename    TEXT NOT NULL,
            FOREIGN KEY (repair_id) REFERENCES repairs (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS label_templates (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT COLLATE NOCASE UNIQUE NOT NULL,
            label_width       REAL NOT NULL,
            label_height      REAL NOT NULL,
            show_qr           INTEGER NOT NULL DEFAULT 1,
            qr_x              REAL NOT NULL DEFAULT 1,
            qr_y              REAL NOT NULL DEFAULT 1,
            qr_size           REAL NOT NULL DEFAULT 16,
            show_serial       INTEGER NOT NULL DEFAULT 1,
            serial_x          REAL NOT NULL DEFAULT 20,
            serial_y          REAL NOT NULL DEFAULT 12,
            serial_font_size  REAL NOT NULL DEFAULT 7,
            static_texts_json TEXT NOT NULL DEFAULT '[]',
            gap_x             REAL NOT NULL DEFAULT 2,
            gap_y             REAL NOT NULL DEFAULT 2,
            margin_top        REAL NOT NULL DEFAULT 10,
            margin_bottom     REAL NOT NULL DEFAULT 10,
            margin_left       REAL NOT NULL DEFAULT 10,
            margin_right      REAL NOT NULL DEFAULT 10,
            created_at        TEXT NOT NULL,
            created_by        TEXT
        );
        """
    )
    db.commit()

    # Lightweight migration: add new columns to an already-existing table
    # without losing existing rows (for people upgrading from an older version).
    existing_columns = {row["name"] for row in db.execute("PRAGMA table_info(label_templates)").fetchall()}
    new_columns = {
        "gap_x": "REAL NOT NULL DEFAULT 2",
        "gap_y": "REAL NOT NULL DEFAULT 2",
        "margin_top": "REAL NOT NULL DEFAULT 10",
        "margin_bottom": "REAL NOT NULL DEFAULT 10",
        "margin_left": "REAL NOT NULL DEFAULT 10",
        "margin_right": "REAL NOT NULL DEFAULT 10",
    }
    for column, coldef in new_columns.items():
        if column not in existing_columns:
            db.execute(f"ALTER TABLE label_templates ADD COLUMN {column} {coldef}")
    db.commit()

    # Create a default admin account on the very first run
    user_count = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if user_count == 0:
        db.execute(
            """INSERT INTO users
               (username, password_hash, can_create, can_delete,
                can_edit_repairs, is_admin, created_at)
               VALUES (?, ?, 1, 1, 1, 1, ?)""",
            ("admin", generate_password_hash("admin"),
             datetime.now().isoformat(timespec="seconds")),
        )
        db.commit()
        print("\n*** Default admin account created: username 'admin', password 'admin' ***")
        print("*** Please change the password after the first login (see 'Mein Konto')! ***\n")

    db.close()


def next_serial_number(db):
    """Generate the next auto serial number, e.g. PL-2026-0007."""
    year = datetime.now().year
    rows = db.execute(
        "SELECT serial_number FROM boards WHERE serial_number LIKE ?",
        (f"PL-{year}-%",),
    ).fetchall()
    highest_number = 0
    for row in rows:
        suffix = row["serial_number"].rsplit("-", 1)[-1]
        if suffix.isdigit():
            highest_number = max(highest_number, int(suffix))
    return f"PL-{year}-{highest_number + 1:04d}"


def split_serial_pattern(serial):
    """Split a serial number into (prefix, numeric_part_as_string).
    e.g. 'PL-2026-0010' -> ('PL-2026-', '0010'). Returns (serial, None) if no
    trailing digits are found."""
    match = re.match(r"^(.*?)(\d+)$", serial)
    if not match:
        return serial, None
    return match.group(1), match.group(2)


def generate_available_serials(db, start_serial, count):
    """Starting from start_serial, count upward and return `count` serial
    numbers that do not yet exist in the database (case-insensitive),
    skipping over any that are already taken."""
    prefix, digits = split_serial_pattern(start_serial)
    if digits is None:
        raise ValueError("Die Start-Seriennummer muss am Ende eine Zahl enthalten.")

    width = len(digits)
    number = int(digits)
    result = []

    while len(result) < count:
        candidate = f"{prefix}{number:0{width}d}"
        exists = db.execute(
            "SELECT 1 FROM boards WHERE serial_number = ? COLLATE NOCASE", (candidate,)
        ).fetchone()
        if not exists:
            result.append(candidate)
        number += 1

    return result


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_or_create_type(db, name):
    name = name.strip()
    row = db.execute("SELECT id FROM board_types WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO board_types (name) VALUES (?)", (name,))
    return cur.lastrowid


def get_or_create_version(db, type_id, name):
    name = name.strip()
    row = db.execute(
        "SELECT id FROM board_versions WHERE type_id = ? AND name = ? COLLATE NOCASE",
        (type_id, name),
    ).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO board_versions (type_id, name) VALUES (?, ?)", (type_id, name))
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Login / permissions
# ---------------------------------------------------------------------------

@app.before_request
def load_current_user():
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


def permission_required(*perms):
    """perm: 'can_create' | 'can_delete' | 'can_edit_repairs' | 'is_admin'"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login", next=request.path))
            if not (g.user["is_admin"] or any(g.user[p] for p in perms)):
                flash("Du hast keine Berechtigung für diese Aktion – nur Ansicht möglich.", "fehler")
                return redirect(request.referrer or url_for("index"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.context_processor
def inject_user():
    # Template variable name kept as 'aktueller_user' would also work, but we
    # standardize on English here since templates are code, not user-facing.
    return {"current_user": g.get("user")}


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("index"))

    if request.method == "POST":
        db = get_db()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            target = request.args.get("next") or url_for("index")
            return redirect(target)
        flash("Benutzername oder Passwort falsch.", "fehler")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        db = get_db()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        new_password_repeat = request.form.get("new_password_repeat", "")

        if not check_password_hash(g.user["password_hash"], current_password):
            flash("Aktuelles Passwort ist falsch.", "fehler")
        elif len(new_password) < 4:
            flash("Neues Passwort muss mindestens 4 Zeichen haben.", "fehler")
        elif new_password != new_password_repeat:
            flash("Die neuen Passwörter stimmen nicht überein.", "fehler")
        else:
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                       (generate_password_hash(new_password), g.user["id"]))
            db.commit()
            flash("Passwort wurde geändert.", "erfolg")
            return redirect(url_for("account"))

    return render_template("account.html")


# ---------------------------------------------------------------------------
# User management (admin only)
# ---------------------------------------------------------------------------

@app.route("/users")
@permission_required("is_admin")
def users_list():
    db = get_db()
    users = db.execute("SELECT * FROM users ORDER BY username COLLATE NOCASE").fetchall()
    return render_template("users.html", users=users)


@app.route("/users/new", methods=["POST"])
@permission_required("is_admin")
def create_user():
    db = get_db()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        flash("Benutzername und Passwort werden benötigt.", "fehler")
        return redirect(url_for("users_list"))

    try:
        db.execute(
            """INSERT INTO users
               (username, password_hash, can_create, can_delete,
                can_edit_repairs, is_admin, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (username, generate_password_hash(password),
             1 if request.form.get("can_create") else 0,
             1 if request.form.get("can_delete") else 0,
             1 if request.form.get("can_edit_repairs") else 0,
             1 if request.form.get("is_admin") else 0,
             datetime.now().isoformat(timespec="seconds")),
        )
        db.commit()
        flash(f"Konto '{username}' wurde angelegt.", "erfolg")
    except sqlite3.IntegrityError:
        flash(f"Benutzername '{username}' existiert bereits.", "fehler")

    return redirect(url_for("users_list"))


@app.route("/users/<int:user_id>/update", methods=["POST"])
@permission_required("is_admin")
def update_user(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        abort(404)

    if user_id == g.user["id"] and not request.form.get("is_admin"):
        flash("Du kannst dir nicht selbst die Admin-Rechte entziehen.", "fehler")
        return redirect(url_for("users_list"))

    db.execute(
        """UPDATE users SET can_create = ?, can_delete = ?,
           can_edit_repairs = ?, is_admin = ? WHERE id = ?""",
        (1 if request.form.get("can_create") else 0,
         1 if request.form.get("can_delete") else 0,
         1 if request.form.get("can_edit_repairs") else 0,
         1 if request.form.get("is_admin") else 0,
         user_id),
    )

    new_password = request.form.get("new_password", "").strip()
    if new_password:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (generate_password_hash(new_password), user_id))

    db.commit()
    flash(f"Konto '{user['username']}' wurde aktualisiert.", "erfolg")
    return redirect(url_for("users_list"))


@app.route("/users/<int:user_id>/delete", methods=["POST"])
@permission_required("is_admin")
def delete_user(user_id):
    if user_id == g.user["id"]:
        flash("Du kannst dein eigenes Konto nicht löschen.", "fehler")
        return redirect(url_for("users_list"))
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    flash("Konto wurde gelöscht.", "erfolg")
    return redirect(url_for("users_list"))


# ---------------------------------------------------------------------------
# Board overview with search & sorting
# ---------------------------------------------------------------------------

SORTABLE_COLUMNS = {
    "serial_number": "b.serial_number COLLATE NOCASE",
    "type": "type_name COLLATE NOCASE",
    "version": "version_name COLLATE NOCASE",
    "count": "repair_count",
    "last_repair": "last_repair_date",
    "created": "b.created_at",
}


@app.route("/")
@login_required
def index():
    db = get_db()
    search = request.args.get("q", "").strip()
    sort = request.args.get("sort", "created")
    direction = request.args.get("dir", "desc")
    if sort not in SORTABLE_COLUMNS:
        sort = "created"
    if direction not in ("asc", "desc"):
        direction = "desc"

    base_query = """
        SELECT b.*,
               t.name AS type_name,
               v.name AS version_name,
               COUNT(r.id) AS repair_count,
               MAX(r.date) AS last_repair_date
        FROM boards b
        LEFT JOIN board_types t ON t.id = b.type_id
        LEFT JOIN board_versions v ON v.id = b.version_id
        LEFT JOIN repairs r ON r.board_id = b.id
    """
    params = []
    if search:
        base_query += " WHERE b.serial_number LIKE ? OR t.name LIKE ? OR v.name LIKE ? "
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    base_query += f" GROUP BY b.id ORDER BY {SORTABLE_COLUMNS[sort]} {direction.upper()}"

    boards = db.execute(base_query, params).fetchall()
    suggested_serial = next_serial_number(db)

    types = db.execute("SELECT * FROM board_types ORDER BY name COLLATE NOCASE").fetchall()
    versions = db.execute("SELECT * FROM board_versions ORDER BY name COLLATE NOCASE").fetchall()

    return render_template(
        "index.html", boards=boards, search=search, suggested_serial=suggested_serial,
        types=types, versions=versions, sort=sort, direction=direction,
    )


@app.route("/boards/new", methods=["POST"])
@permission_required("can_create")
def create_board():
    db = get_db()
    serial_number = request.form.get("serial_number", "").strip()
    if not serial_number:
        serial_number = next_serial_number(db)

    type_choice = request.form.get("type_id", "")
    new_type_name = request.form.get("new_type", "").strip()
    version_choice = request.form.get("version_id", "")
    new_version_name = request.form.get("new_version", "").strip()

    type_id = None
    version_id = None

    if type_choice == "__new__" and new_type_name:
        type_id = get_or_create_type(db, new_type_name)
    elif type_choice.isdigit():
        type_id = int(type_choice)

    if type_id is not None:
        if version_choice == "__new__" and new_version_name:
            version_id = get_or_create_version(db, type_id, new_version_name)
        elif version_choice.isdigit():
            version_id = int(version_choice)

    # Case-insensitive duplicate check (in addition to the DB constraint, for a clear message)
    existing = db.execute(
        "SELECT id FROM boards WHERE serial_number = ? COLLATE NOCASE", (serial_number,)
    ).fetchone()
    if existing:
        flash(f"Eine Platine mit der Seriennummer '{serial_number}' existiert bereits "
              f"(Groß-/Kleinschreibung wird ignoriert).", "fehler")
        return redirect(url_for("index"))

    cur = db.execute(
        "INSERT INTO boards (serial_number, type_id, version_id, created_at, created_by) "
        "VALUES (?, ?, ?, ?, ?)",
        (serial_number, type_id, version_id, datetime.now().isoformat(timespec="seconds"),
         g.user["username"]),
    )
    db.commit()
    flash(f"Platine '{serial_number}' wurde angelegt.", "erfolg")
    if request.form.get("AddButton") == "create_and_add":
        return redirect(url_for("board_detail", board_id=cur.lastrowid))
    return redirect(url_for("index"))


@app.route("/types/<int:type_id>/versions")
@login_required
def versions_for_type(type_id):
    """Small JSON helper for the cascading dropdown (fallback in case JS needs it)."""
    db = get_db()
    versions = db.execute(
        "SELECT id, name FROM board_versions WHERE type_id = ? ORDER BY name COLLATE NOCASE",
        (type_id,),
    ).fetchall()
    return {"versions": [{"id": v["id"], "name": v["name"]} for v in versions]}


@app.route("/boards/<int:board_id>")
@login_required
def board_detail(board_id):
    db = get_db()
    board = db.execute(
        """SELECT b.*, t.name AS type_name, v.name AS version_name
           FROM boards b
           LEFT JOIN board_types t ON t.id = b.type_id
           LEFT JOIN board_versions v ON v.id = b.version_id
           WHERE b.id = ?""",
        (board_id,),
    ).fetchone()
    if board is None:
        abort(404)

    repairs = db.execute(
        "SELECT * FROM repairs WHERE board_id = ? ORDER BY date DESC, id DESC",
        (board_id,),
    ).fetchall()

    repairs_with_attachments = []
    for repair in repairs:
        attachments = db.execute(
            "SELECT * FROM repair_attachments WHERE repair_id = ?", (repair["id"],)
        ).fetchall()
        repairs_with_attachments.append({"repair": repair, "attachments": attachments})

    return render_template(
        "board.html",
        board=board,
        repairs=repairs_with_attachments,
        today=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/boards/<int:board_id>/repairs", methods=["POST"])
@permission_required("can_edit_repairs", "can_create")
def create_repair(board_id):
    db = get_db()
    board = db.execute("SELECT * FROM boards WHERE id = ?", (board_id,)).fetchone()
    if board is None:
        abort(404)

    date = request.form.get("date") or datetime.now().strftime("%Y-%m-%d")
    issue_description = request.form.get("issue_description", "").strip()
    action_taken = request.form.get("action_taken", "").strip()
    technician = request.form.get("technician", "").strip()
    parts = request.form.get("parts", "").strip()
    ticket = request.form.get("ticket", "").strip()
    customer = request.form.get("customer", "").strip()
    
    cur = db.execute(
        """INSERT INTO repairs
           (board_id, date, issue_description, action_taken, technician, parts, ticket, customer, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (board_id, date, issue_description, action_taken, technician, parts, ticket, customer,
         datetime.now().isoformat(timespec="seconds")),
    )
    repair_id = cur.lastrowid

    files = request.files.getlist("attachments")
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            safe_name = secure_filename(file.filename)
            unique_name = f"{board_id}_{repair_id}_{int(datetime.now().timestamp())}_{safe_name}"
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
            db.execute(
                "INSERT INTO repair_attachments (repair_id, filename) VALUES (?, ?)",
                (repair_id, unique_name),
            )

    db.commit()
    flash("Reparatur-Eintrag wurde hinzugefügt.", "erfolg")
    return redirect(url_for("board_detail", board_id=board_id))


@app.route("/repairs/<int:repair_id>/edit", methods=["GET", "POST"])
@permission_required("can_edit_repairs")
def edit_repair(repair_id):
    db = get_db()
    repair = db.execute("SELECT * FROM repairs WHERE id = ?", (repair_id,)).fetchone()
    if repair is None:
        abort(404)

    if request.method == "POST":
        date = request.form.get("date") or repair["date"]
        issue_description = request.form.get("issue_description", "").strip()
        action_taken = request.form.get("action_taken", "").strip()
        technician = request.form.get("technician", "").strip()
        parts = request.form.get("parts", "").strip()

        db.execute(
            """UPDATE repairs SET date = ?, issue_description = ?, action_taken = ?,
               technician = ?, parts = ?, updated_at = ?, updated_by = ?
               WHERE id = ?""",
            (date, issue_description, action_taken, technician, parts,
             datetime.now().isoformat(timespec="seconds"), g.user["username"], repair_id),
        )

        files = request.files.getlist("attachments")
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                safe_name = secure_filename(file.filename)
                unique_name = f"{repair['board_id']}_{repair_id}_{int(datetime.now().timestamp())}_{safe_name}"
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
                db.execute(
                    "INSERT INTO repair_attachments (repair_id, filename) VALUES (?, ?)",
                    (repair_id, unique_name),
                )

        attachment_ids_to_delete = request.form.getlist("delete_attachment")
        for attachment_id in attachment_ids_to_delete:
            attachment = db.execute(
                "SELECT * FROM repair_attachments WHERE id = ?", (attachment_id,)
            ).fetchone()
            if attachment:
                path = os.path.join(app.config["UPLOAD_FOLDER"], attachment["filename"])
                if os.path.exists(path):
                    os.remove(path)
                db.execute("DELETE FROM repair_attachments WHERE id = ?", (attachment_id,))

        db.commit()
        flash("Reparatur-Eintrag wurde aktualisiert.", "erfolg")
        return redirect(url_for("board_detail", board_id=repair["board_id"]))

    attachments = db.execute(
        "SELECT * FROM repair_attachments WHERE repair_id = ?", (repair_id,)
    ).fetchall()
    return render_template("edit_repair.html", repair=repair, attachments=attachments)


@app.route("/boards/<int:board_id>/delete", methods=["POST"])
@permission_required("can_delete")
def delete_board(board_id):
    db = get_db()
    board = db.execute("SELECT * FROM boards WHERE id = ?", (board_id,)).fetchone()
    if board is None:
        abort(404)
    db.execute("DELETE FROM boards WHERE id = ?", (board_id,))
    db.commit()
    flash(f"Platine '{board['serial_number']}' wurde gelöscht.", "erfolg")
    return redirect(url_for("index"))


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/uploads/<path:filename>/download")
@login_required
def download_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


@app.route("/boards/<int:board_id>/qrcode.png")
@login_required
def board_qrcode(board_id):
    db = get_db()
    board = db.execute("SELECT * FROM boards WHERE id = ?", (board_id,)).fetchone()
    if board is None:
        abort(404)

    ## QR-Code to Repair Site (Settings)
    #qr_content = request.host_url.rstrip("/") + url_for("board_detail", board_id=board_id)
    ## QR-Code = serialnumber
    qr_content = board["serial_number"]
    img = qrcode.make(qr_content, box_size=8, border=2)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


# ---------------------------------------------------------------------------
# Label sheet generator (QR code stickers as a DIN A4 PDF)
# ---------------------------------------------------------------------------

LABEL_DEFAULTS = {
    "label_width": 40, "label_height": 20,
    "gap_x": 2, "gap_y": 2,
    "margin_top": 10, "margin_bottom": 10, "margin_left": 10, "margin_right": 10,
    "count": 1, "start_position": 1,
}


def compute_label_grid(label_width, label_height, gap_x, gap_y,
                        margin_top, margin_bottom, margin_left, margin_right):
    """Work out how many label columns/rows fit on one A4 page for the
    given sizes (all values in millimetres)."""
    page_width_mm = A4[0] / mm
    page_height_mm = A4[1] / mm

    usable_width = page_width_mm - margin_left - margin_right
    usable_height = page_height_mm - margin_top - margin_bottom

    columns = max(1, int((usable_width + gap_x) // (label_width + gap_x)))
    rows = max(1, int((usable_height + gap_y) // (label_height + gap_y)))
    return columns, rows


@app.route("/labels/preview-qr")
@permission_required("can_create")
def labels_preview_qr():
    """Return a QR code PNG for arbitrary text, used for the live single-label
    preview on the labels page (the serial number may not exist as a board yet)."""
    text = request.args.get("text", "").strip() or "PL-0000-0000"
    img = qrcode.make(text, box_size=6, border=1)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


def get_label_templates(db):
    return db.execute(
        "SELECT * FROM label_templates ORDER BY name COLLATE NOCASE"
    ).fetchall()


def template_row_to_elements(template_row):
    """Convert a label_templates DB row into the same 'elements' dict shape
    that parse_label_elements() produces from the editor form."""
    return {
        "show_qr": bool(template_row["show_qr"]),
        "qr_x": template_row["qr_x"], "qr_y": template_row["qr_y"], "qr_size": template_row["qr_size"],
        "show_serial": bool(template_row["show_serial"]),
        "serial_x": template_row["serial_x"], "serial_y": template_row["serial_y"],
        "serial_font_size": template_row["serial_font_size"],
        "static_texts": json.loads(template_row["static_texts_json"]),
    }


@app.route("/labels/templates/save", methods=["POST"])
@permission_required("is_admin")
def labels_template_save():
    db = get_db()
    name = request.form.get("template_name", "").strip()
    if not name:
        flash("Bitte einen Namen für die Vorlage angeben.", "fehler")
        return redirect(url_for("labels_page"))

    try:
        label_width = float(request.form.get("label_width"))
        label_height = float(request.form.get("label_height"))
        gap_x = float(request.form.get("gap_x"))
        gap_y = float(request.form.get("gap_y"))
        margin_top = float(request.form.get("margin_top"))
        margin_bottom = float(request.form.get("margin_bottom"))
        margin_left = float(request.form.get("margin_left"))
        margin_right = float(request.form.get("margin_right"))
        elements = parse_label_elements(request.form, label_height)
    except (TypeError, ValueError):
        flash("Bitte alle Felder der Vorlage mit gültigen Zahlen ausfüllen.", "fehler")
        return redirect(url_for("labels_page"))

    static_texts_json = json.dumps(elements["static_texts"])
    existing = db.execute(
        "SELECT id FROM label_templates WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()

    if existing:
        db.execute(
            """UPDATE label_templates SET
                 label_width = ?, label_height = ?,
                 show_qr = ?, qr_x = ?, qr_y = ?, qr_size = ?,
                 show_serial = ?, serial_x = ?, serial_y = ?, serial_font_size = ?,
                 static_texts_json = ?,
                 gap_x = ?, gap_y = ?,
                 margin_top = ?, margin_bottom = ?, margin_left = ?, margin_right = ?
               WHERE id = ?""",
            (label_width, label_height,
             1 if elements["show_qr"] else 0, elements["qr_x"], elements["qr_y"], elements["qr_size"],
             1 if elements["show_serial"] else 0, elements["serial_x"], elements["serial_y"],
             elements["serial_font_size"], static_texts_json,
             gap_x, gap_y, margin_top, margin_bottom, margin_left, margin_right,
             existing["id"]),
        )
        flash(f"Vorlage '{name}' wurde aktualisiert.", "erfolg")
    else:
        db.execute(
            """INSERT INTO label_templates
               (name, label_width, label_height, show_qr, qr_x, qr_y, qr_size,
                show_serial, serial_x, serial_y, serial_font_size, static_texts_json,
                gap_x, gap_y, margin_top, margin_bottom, margin_left, margin_right,
                created_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, label_width, label_height,
             1 if elements["show_qr"] else 0, elements["qr_x"], elements["qr_y"], elements["qr_size"],
             1 if elements["show_serial"] else 0, elements["serial_x"], elements["serial_y"],
             elements["serial_font_size"], static_texts_json,
             gap_x, gap_y, margin_top, margin_bottom, margin_left, margin_right,
             datetime.now().isoformat(timespec="seconds"), g.user["username"]),
        )
        flash(f"Vorlage '{name}' wurde angelegt.", "erfolg")

    db.commit()
    return redirect(url_for("labels_page"))


@app.route("/labels/templates/<int:template_id>/delete", methods=["POST"])
@permission_required("is_admin")
def labels_template_delete(template_id):
    db = get_db()
    template_row = db.execute("SELECT * FROM label_templates WHERE id = ?", (template_id,)).fetchone()
    if template_row is None:
        abort(404)
    db.execute("DELETE FROM label_templates WHERE id = ?", (template_id,))
    db.commit()
    flash(f"Vorlage '{template_row['name']}' wurde gelöscht.", "erfolg")
    return redirect(url_for("labels_page"))


@app.route("/labels")
@permission_required("can_create")
def labels_page():
    db = get_db()
    suggested_serial = next_serial_number(db)
    templates = get_label_templates(db)
    templates_json = json.dumps([{
        "id": t["id"], "name": t["name"],
        "label_width": t["label_width"], "label_height": t["label_height"],
        "show_qr": bool(t["show_qr"]), "qr_x": t["qr_x"], "qr_y": t["qr_y"], "qr_size": t["qr_size"],
        "show_serial": bool(t["show_serial"]), "serial_x": t["serial_x"], "serial_y": t["serial_y"],
        "serial_font_size": t["serial_font_size"],
        "static_texts": json.loads(t["static_texts_json"]),
        "gap_x": t["gap_x"], "gap_y": t["gap_y"],
        "margin_top": t["margin_top"], "margin_bottom": t["margin_bottom"],
        "margin_left": t["margin_left"], "margin_right": t["margin_right"],
    } for t in templates])

    columns, rows = compute_label_grid(
        LABEL_DEFAULTS["label_width"], LABEL_DEFAULTS["label_height"],
        LABEL_DEFAULTS["gap_x"], LABEL_DEFAULTS["gap_y"],
        LABEL_DEFAULTS["margin_top"], LABEL_DEFAULTS["margin_bottom"],
        LABEL_DEFAULTS["margin_left"], LABEL_DEFAULTS["margin_right"],
    )
    return render_template(
        "labels.html", defaults=LABEL_DEFAULTS, suggested_serial=suggested_serial,
        columns=columns, rows=rows, templates=templates, templates_json=templates_json,
    )


@app.route("/labels/preview-grid")
@permission_required("can_create")
def labels_preview_grid():
    """Small JSON helper so the form can live-update the columns/rows preview."""
    try:
        columns, rows = compute_label_grid(
            float(request.args.get("label_width", 40)),
            float(request.args.get("label_height", 20)),
            float(request.args.get("gap_x", 2)),
            float(request.args.get("gap_y", 2)),
            float(request.args.get("margin_top", 10)),
            float(request.args.get("margin_bottom", 10)),
            float(request.args.get("margin_left", 10)),
            float(request.args.get("margin_right", 10)),
        )
    except (TypeError, ValueError):
        return {"columns": 0, "rows": 0, "per_page": 0}
    return {"columns": columns, "rows": rows, "per_page": columns * rows}


def label_topleft_to_pdf(label_x_pdf, label_y_pdf, label_height_mm, x_mm, y_mm):
    """Convert a position given as (x_mm, y_mm) measured from the TOP-LEFT
    corner of a label into absolute PDF coordinates (PDF's origin is
    bottom-left of the page). label_x_pdf/label_y_pdf is the label's own
    bottom-left corner in PDF points."""
    pdf_x = label_x_pdf + x_mm * mm
    pdf_y = label_y_pdf + (label_height_mm - y_mm) * mm
    return pdf_x, pdf_y


def parse_label_elements(form, label_height_mm):
    """Read the QR code / serial number / static text field settings that
    were configured in the visual label editor."""
    elements = {"show_qr": form.get("show_qr") == "on", "show_serial": form.get("show_serial") == "on"}

    elements["qr_x"] = float(form.get("qr_x", 1))
    elements["qr_y"] = float(form.get("qr_y", 1))
    elements["qr_size"] = float(form.get("qr_size", 16))

    elements["serial_x"] = float(form.get("serial_x", 20))
    elements["serial_y"] = float(form.get("serial_y", 12))
    elements["serial_font_size"] = float(form.get("serial_font_size", 7))

    texts = form.getlist("static_text[]")
    xs = form.getlist("static_text_x[]")
    ys = form.getlist("static_text_y[]")
    sizes = form.getlist("static_text_size[]")

    static_texts = []
    for content, x, y, size in zip(texts, xs, ys, sizes):
        content = content.strip()
        if not content:
            continue
        static_texts.append({
            "content": content,
            "x": float(x), "y": float(y), "font_size": float(size),
        })
    elements["static_texts"] = static_texts
    return elements


@app.route("/labels/generate", methods=["POST"])
@permission_required("can_create")
def labels_generate():
    db = get_db()

    template_id = request.form.get("template_id")
    template_row = db.execute(
        "SELECT * FROM label_templates WHERE id = ?", (template_id,)
    ).fetchone() if template_id else None

    if template_row is None:
        flash("Bitte eine Etikett-Vorlage auswählen.", "fehler")
        return redirect(url_for("labels_page"))

    label_width = template_row["label_width"]
    label_height = template_row["label_height"]
    elements = template_row_to_elements(template_row)

    try:
        gap_x = float(request.form.get("gap_x"))
        gap_y = float(request.form.get("gap_y"))
        margin_top = float(request.form.get("margin_top"))
        margin_bottom = float(request.form.get("margin_bottom"))
        margin_left = float(request.form.get("margin_left"))
        margin_right = float(request.form.get("margin_right"))
        count = int(request.form.get("count"))
        start_position = int(request.form.get("start_position"))
        start_serial = request.form.get("start_serial", "").strip()
    except (TypeError, ValueError):
        flash("Bitte alle Felder mit gültigen Zahlen ausfüllen.", "fehler")
        return redirect(url_for("labels_page"))

    if not start_serial:
        flash("Bitte eine Start-Seriennummer angeben.", "fehler")
        return redirect(url_for("labels_page"))
    if count < 1 or count > 500:
        flash("Anzahl muss zwischen 1 und 500 liegen.", "fehler")
        return redirect(url_for("labels_page"))
    if start_position < 1:
        flash("Startposition muss mindestens 1 sein.", "fehler")
        return redirect(url_for("labels_page"))

    columns, rows = compute_label_grid(
        label_width, label_height, gap_x, gap_y,
        margin_top, margin_bottom, margin_left, margin_right,
    )
    labels_per_page = columns * rows
    if start_position > labels_per_page:
        flash(f"Startposition ({start_position}) liegt außerhalb des Rasters "
              f"({labels_per_page} Etiketten pro Seite).", "fehler")
        return redirect(url_for("labels_page"))

    try:
        serials = generate_available_serials(db, start_serial, count)
    except ValueError as e:
        flash(str(e), "fehler")
        return redirect(url_for("labels_page"))

    page_width, page_height = A4
    buffer = BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=A4)

    position = start_position
    is_first_label = True

    for serial in serials:
        pos_on_page = (position - 1) % labels_per_page
        if pos_on_page == 0 and not is_first_label:
            c.showPage()
        is_first_label = False

        col = pos_on_page % columns
        row = pos_on_page // columns

        label_x = (margin_left + col * (label_width + gap_x)) * mm
        label_y = page_height - (margin_top + (row + 1) * label_height + row * gap_y) * mm

        # QR code
        if elements["show_qr"]:
            qr_img = qrcode.make(serial, box_size=6, border=1)
            qr_buffer = BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)

            qr_size_pt = elements["qr_size"] * mm
            qr_pdf_x, qr_top_pdf_y = label_topleft_to_pdf(
                label_x, label_y, label_height, elements["qr_x"], elements["qr_y"]
            )
            qr_pdf_y = qr_top_pdf_y - qr_size_pt  # drawImage wants the bottom-left corner
            c.drawImage(ImageReader(qr_buffer), qr_pdf_x, qr_pdf_y,
                        width=qr_size_pt, height=qr_size_pt, mask="auto")

        # Serial number text
        if elements["show_serial"]:
            serial_pdf_x, serial_pdf_y = label_topleft_to_pdf(
                label_x, label_y, label_height, elements["serial_x"], elements["serial_y"]
            )
            c.setFont("Helvetica", elements["serial_font_size"])
            c.drawString(serial_pdf_x, serial_pdf_y, serial)

        # Static text fields (same content on every label)
        for field in elements["static_texts"]:
            field_pdf_x, field_pdf_y = label_topleft_to_pdf(
                label_x, label_y, label_height, field["x"], field["y"]
            )
            c.setFont("Helvetica", field["font_size"])
            c.drawString(field_pdf_x, field_pdf_y, field["content"])

        # Outline for cutting/alignment help
        c.setLineWidth(0.2)
        c.rect(label_x, label_y, label_width * mm, label_height * mm)

        position += 1

    c.save()
    buffer.seek(0)
    return send_file(
        buffer, mimetype="application/pdf", as_attachment=True,
        download_name="etiketten.pdf",
    )


# ---------------------------------------------------------------------------
# Entry point
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
