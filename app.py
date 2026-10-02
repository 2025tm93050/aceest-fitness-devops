"""ACEest Fitness & Gym - Flask web application.

REST API for managing gym clients, programs, workouts, progress and metrics.
Business rules live in fitness.py; this module handles HTTP and storage.
"""

import os
import sqlite3
from datetime import date

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

import fitness

APP_VERSION = "1.0.0"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    age INTEGER,
    height REAL,
    weight REAL,
    program TEXT,
    calories INTEGER,
    target_weight REAL,
    target_adherence INTEGER,
    membership_end TEXT
);
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    week TEXT NOT NULL,
    adherence INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    workout_type TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sets INTEGER,
    reps INTEGER,
    weight REAL
);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    weight REAL,
    waist REAL,
    bodyfat REAL
);
"""


class ValidationError(Exception):
    """Raised when request data is invalid; returned to the caller as HTTP 400."""


# ---------- DATABASE ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(g.database)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(database, admin_password):
    conn = sqlite3.connect(database)
    try:
        conn.executescript(SCHEMA)
        exists = conn.execute("SELECT 1 FROM users WHERE username = 'admin'").fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", generate_password_hash(admin_password), "Admin"),
            )
        conn.commit()
    finally:
        conn.close()


# ---------- VALIDATION HELPERS ----------
def get_json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    return data


def number_field(data, key, required=False, minimum=0, maximum=None, integer=False):
    value = data.get(key)
    if value is None:
        if required:
            raise ValidationError(f"'{key}' is required")
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"'{key}' must be a number")
    if integer and int(value) != value:
        raise ValidationError(f"'{key}' must be a whole number")
    if value < minimum or (maximum is not None and value > maximum):
        limit = f"between {minimum} and {maximum}" if maximum is not None else f">= {minimum}"
        raise ValidationError(f"'{key}' must be {limit}")
    return int(value) if integer else float(value)


def text_field(data, key, required=False):
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"'{key}' is required")
        return None
    if not isinstance(value, str):
        raise ValidationError(f"'{key}' must be a string")
    return value.strip()


def date_field(data, key, required=False, default=None):
    value = text_field(data, key)
    if value is None:
        if required and default is None:
            raise ValidationError(f"'{key}' is required")
        return default
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"'{key}' must be a date in YYYY-MM-DD format") from None
    return value


def program_field(data, key="program", required=False):
    value = text_field(data, key, required=required)
    if value is None:
        return None
    if fitness.get_program(value) is None:
        raise ValidationError(f"'{key}' must be one of {sorted(fitness.PROGRAMS)}")
    return value.upper()


# ---------- SERIALISERS ----------
def client_to_dict(row):
    client = dict(row)
    client["membership_status"] = fitness.membership_status(client["membership_end"])
    return client


def find_client(client_id):
    return get_db().execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()


def not_found(what="Client"):
    return jsonify(error=f"{what} not found"), 404


# ---------- APPLICATION FACTORY ----------
def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get("ACEEST_DB", "aceest_fitness.db"),
        ADMIN_PASSWORD=os.environ.get("ACEEST_ADMIN_PASSWORD", "admin"),
    )
    if config:
        app.config.update(config)

    init_db(app.config["DATABASE"], app.config["ADMIN_PASSWORD"])

    @app.before_request
    def _set_database():
        g.database = app.config["DATABASE"]

    app.teardown_appcontext(close_db)

    @app.errorhandler(ValidationError)
    def _validation_error(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(404)
    def _not_found(_exc):
        return jsonify(error="Resource not found"), 404

    @app.errorhandler(405)
    def _method_not_allowed(_exc):
        return jsonify(error="Method not allowed"), 405

    # ----- General -----
    @app.get("/")
    def index():
        return jsonify(
            app="ACEest Fitness & Gym",
            version=APP_VERSION,
            endpoints=[
                "GET /health",
                "POST /login",
                "GET /programs",
                "GET /programs/<code>",
                "GET|POST /clients",
                "GET|PUT|DELETE /clients/<id>",
                "GET /clients/<id>/bmi",
                "POST /clients/<id>/program",
                "GET /clients/<id>/membership",
                "GET|POST /clients/<id>/progress",
                "GET|POST /clients/<id>/workouts",
                "GET|POST /clients/<id>/metrics",
            ],
        )

    @app.get("/health")
    def health():
        get_db().execute("SELECT 1")
        return jsonify(status="ok", version=APP_VERSION)

    @app.post("/login")
    def login():
        data = get_json_body()
        username = text_field(data, "username", required=True)
        password = text_field(data, "password", required=True)
        row = get_db().execute(
            "SELECT password_hash, role FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None or not check_password_hash(row["password_hash"], password):
            return jsonify(error="Invalid credentials"), 401
        return jsonify(username=username, role=row["role"])

    # ----- Programs -----
    @app.get("/programs")
    def list_programs():
        return jsonify(
            [
                {"code": code, "name": p["name"], "calorie_factor": p["calorie_factor"]}
                for code, p in fitness.PROGRAMS.items()
            ]
        )

    @app.get("/programs/<code>")
    def get_program(code):
        program = fitness.get_program(code)
        if program is None:
            return not_found("Program")
        return jsonify(code=code.upper(), **program)

    # ----- Clients -----
    def read_client_fields(data, partial):
        fields = {
            "age": number_field(data, "age", minimum=1, maximum=120, integer=True),
            "height": number_field(data, "height", minimum=50, maximum=272),
            "weight": number_field(data, "weight", minimum=1, maximum=500),
            "program": program_field(data),
            "target_weight": number_field(data, "target_weight", minimum=1, maximum=500),
            "target_adherence": number_field(
                data, "target_adherence", minimum=0, maximum=100, integer=True
            ),
            "membership_end": date_field(data, "membership_end"),
        }
        if partial:
            fields = {k: v for k, v in fields.items() if k in data}
        return fields

    @app.get("/clients")
    def list_clients():
        rows = get_db().execute("SELECT * FROM clients ORDER BY name").fetchall()
        return jsonify([client_to_dict(r) for r in rows])

    @app.post("/clients")
    def create_client():
        data = get_json_body()
        name = text_field(data, "name", required=True)
        fields = read_client_fields(data, partial=False)
        if fields["weight"] and fields["program"]:
            fields["calories"] = fitness.calculate_calories(fields["weight"], fields["program"])
        db = get_db()
        columns = ["name"] + list(fields)
        try:
            cur = db.execute(
                f"INSERT INTO clients ({', '.join(columns)}) "
                f"VALUES ({', '.join('?' * len(columns))})",
                [name] + list(fields.values()),
            )
        except sqlite3.IntegrityError:
            return jsonify(error=f"Client '{name}' already exists"), 409
        db.commit()
        return jsonify(client_to_dict(find_client(cur.lastrowid))), 201

    @app.get("/clients/<int:client_id>")
    def get_client(client_id):
        row = find_client(client_id)
        if row is None:
            return not_found()
        return jsonify(client_to_dict(row))

    @app.put("/clients/<int:client_id>")
    def update_client(client_id):
        row = find_client(client_id)
        if row is None:
            return not_found()
        updates = read_client_fields(get_json_body(), partial=True)
        merged = {**dict(row), **updates}
        if merged["weight"] and merged["program"]:
            updates["calories"] = fitness.calculate_calories(merged["weight"], merged["program"])
        if updates:
            db = get_db()
            db.execute(
                f"UPDATE clients SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = ?",
                list(updates.values()) + [client_id],
            )
            db.commit()
        return jsonify(client_to_dict(find_client(client_id)))

    @app.delete("/clients/<int:client_id>")
    def delete_client(client_id):
        if find_client(client_id) is None:
            return not_found()
        db = get_db()
        db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        db.commit()
        return "", 204

    @app.get("/clients/<int:client_id>/bmi")
    def client_bmi(client_id):
        row = find_client(client_id)
        if row is None:
            return not_found()
        if not row["weight"] or not row["height"]:
            raise ValidationError("Client needs height and weight to calculate BMI")
        bmi = fitness.calculate_bmi(row["weight"], row["height"])
        category, risk = fitness.bmi_category(bmi)
        return jsonify(client_id=client_id, bmi=bmi, category=category, risk=risk)

    @app.post("/clients/<int:client_id>/program")
    def client_generate_program(client_id):
        row = find_client(client_id)
        if row is None:
            return not_found()
        data = request.get_json(silent=True) or {}
        code = program_field(data) or row["program"]
        result = fitness.generate_program(code)
        updates = {"program": result["program"]}
        if row["weight"]:
            updates["calories"] = fitness.calculate_calories(row["weight"], result["program"])
        db = get_db()
        db.execute(
            f"UPDATE clients SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = ?",
            list(updates.values()) + [client_id],
        )
        db.commit()
        return jsonify(client_id=client_id, **result)

    @app.get("/clients/<int:client_id>/membership")
    def client_membership(client_id):
        row = find_client(client_id)
        if row is None:
            return not_found()
        return jsonify(
            client_id=client_id,
            status=fitness.membership_status(row["membership_end"]),
            renewal_date=row["membership_end"],
        )

    # ----- Progress -----
    @app.route("/clients/<int:client_id>/progress", methods=["GET", "POST"])
    def client_progress(client_id):
        if find_client(client_id) is None:
            return not_found()
        db = get_db()
        if request.method == "POST":
            data = get_json_body()
            week = text_field(data, "week", required=True)
            adherence = number_field(
                data, "adherence", required=True, minimum=0, maximum=100, integer=True
            )
            db.execute(
                "INSERT INTO progress (client_id, week, adherence) VALUES (?, ?, ?)",
                (client_id, week, adherence),
            )
            db.commit()
        rows = db.execute(
            "SELECT week, adherence FROM progress WHERE client_id = ? ORDER BY id", (client_id,)
        ).fetchall()
        body = {
            "client_id": client_id,
            "entries": [dict(r) for r in rows],
            "average_adherence": fitness.average_adherence(r["adherence"] for r in rows),
        }
        return jsonify(body), 201 if request.method == "POST" else 200

    # ----- Workouts -----
    @app.route("/clients/<int:client_id>/workouts", methods=["GET", "POST"])
    def client_workouts(client_id):
        if find_client(client_id) is None:
            return not_found()
        db = get_db()
        if request.method == "POST":
            data = get_json_body()
            workout_date = date_field(data, "date", default=date.today().isoformat())
            workout_type = text_field(data, "workout_type", required=True)
            if workout_type not in fitness.WORKOUT_TYPES:
                raise ValidationError(f"'workout_type' must be one of {list(fitness.WORKOUT_TYPES)}")
            duration = number_field(
                data, "duration_min", required=True, minimum=1, maximum=600, integer=True
            )
            exercises = data.get("exercises", [])
            if not isinstance(exercises, list):
                raise ValidationError("'exercises' must be a list")
            parsed = [
                (
                    text_field(ex, "name", required=True),
                    number_field(ex, "sets", minimum=1, integer=True),
                    number_field(ex, "reps", minimum=1, integer=True),
                    number_field(ex, "weight", minimum=0),
                )
                for ex in (e if isinstance(e, dict) else {} for e in exercises)
            ]
            cur = db.execute(
                "INSERT INTO workouts (client_id, date, workout_type, duration_min, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                (client_id, workout_date, workout_type, duration, text_field(data, "notes")),
            )
            db.executemany(
                "INSERT INTO exercises (workout_id, name, sets, reps, weight) VALUES (?, ?, ?, ?, ?)",
                [(cur.lastrowid, *ex) for ex in parsed],
            )
            db.commit()
        workouts = []
        for w in db.execute(
            "SELECT * FROM workouts WHERE client_id = ? ORDER BY date DESC, id DESC", (client_id,)
        ).fetchall():
            item = dict(w)
            item["exercises"] = [
                dict(e)
                for e in db.execute(
                    "SELECT name, sets, reps, weight FROM exercises WHERE workout_id = ? ORDER BY id",
                    (w["id"],),
                ).fetchall()
            ]
            workouts.append(item)
        if request.method == "POST":
            return jsonify(workouts[0] if workouts else {}), 201
        return jsonify(workouts)

    # ----- Body metrics -----
    @app.route("/clients/<int:client_id>/metrics", methods=["GET", "POST"])
    def client_metrics(client_id):
        if find_client(client_id) is None:
            return not_found()
        db = get_db()
        if request.method == "POST":
            data = get_json_body()
            values = (
                client_id,
                date_field(data, "date", default=date.today().isoformat()),
                number_field(data, "weight", minimum=1, maximum=500),
                number_field(data, "waist", minimum=1, maximum=300),
                number_field(data, "bodyfat", minimum=1, maximum=75),
            )
            if all(v is None for v in values[2:]):
                raise ValidationError("Provide at least one of 'weight', 'waist', 'bodyfat'")
            cur = db.execute(
                "INSERT INTO metrics (client_id, date, weight, waist, bodyfat) VALUES (?, ?, ?, ?, ?)",
                values,
            )
            db.commit()
            row = db.execute("SELECT * FROM metrics WHERE id = ?", (cur.lastrowid,)).fetchone()
            return jsonify(dict(row)), 201
        rows = db.execute(
            "SELECT * FROM metrics WHERE client_id = ? ORDER BY date, id", (client_id,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    create_app().run(host="0.0.0.0", port=port)
