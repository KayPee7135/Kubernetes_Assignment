import os
import time

import psycopg
from flask import Flask, jsonify, request
from psycopg.rows import dict_row

app = Flask(__name__)

def connect():
    return psycopg.connect(host=os.environ.get("DB_HOST", "postgres"), port=os.environ.get("DB_PORT", "5432"), dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], connect_timeout=2, row_factory=dict_row)

def initialize_database():
    for attempt in range(30):
        try:
            with connect() as conn, conn.cursor() as cur:
                cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE)")
            return
        except psycopg.OperationalError:
            if attempt == 29:
                raise
            time.sleep(2)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}, 200

@app.get("/ready")
def ready():
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "ready"}, 200
    except psycopg.Error:
        return {"status": "not ready"}, 503

@app.get("/users")
def list_users():
    with connect() as conn:
        rows = conn.execute("SELECT id, name, email FROM users ORDER BY id").fetchall()
    return jsonify(rows)

@app.post("/users")
def create_user():
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("email"):
        return {"error": "name and email are required"}, 400
    try:
        with connect() as conn:
            row = conn.execute("INSERT INTO users (name, email) VALUES (%s, %s) RETURNING id, name, email", (data["name"], data["email"])).fetchone()
        return jsonify(row), 201
    except psycopg.errors.UniqueViolation:
        return {"error": "email already exists"}, 409

@app.get("/users/<int:user_id>")
def get_user(user_id):
    with connect() as conn:
        row = conn.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,)).fetchone()
    return (jsonify(row), 200) if row else ({"error": "user not found"}, 404)

@app.put("/users/<int:user_id>")
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("email"):
        return {"error": "name and email are required"}, 400
    try:
        with connect() as conn:
            row = conn.execute("UPDATE users SET name = %s, email = %s WHERE id = %s RETURNING id, name, email", (data["name"], data["email"], user_id)).fetchone()
        return (jsonify(row), 200) if row else ({"error": "user not found"}, 404)
    except psycopg.errors.UniqueViolation:
        return {"error": "email already exists"}, 409

@app.delete("/users/<int:user_id>")
def delete_user(user_id):
    with connect() as conn:
        row = conn.execute("DELETE FROM users WHERE id = %s RETURNING id, name, email", (user_id,)).fetchone()
    return (jsonify(row), 200) if row else ({"error": "user not found"}, 404)

if __name__ == "__main__":
    initialize_database()
    app.run(host="0.0.0.0", port=8080)
