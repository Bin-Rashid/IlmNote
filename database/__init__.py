import sqlite3
import os
from flask import g
from config import Config

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(Config.DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db(app):
    """Create tables if they don't exist. Never overwrites user data."""
    fresh = not os.path.exists(Config.DATABASE)
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

    conn = sqlite3.connect(Config.DATABASE)
    with open(os.path.join(os.path.dirname(__file__), "schema.sql"), "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    # Seed only when DB is brand-new
    if fresh:
        with open(os.path.join(os.path.dirname(__file__), "seed.sql"), "r", encoding="utf-8") as f:
            conn.executescript(f.read())

    conn.commit()
    conn.close()
    app.teardown_appcontext(close_db)