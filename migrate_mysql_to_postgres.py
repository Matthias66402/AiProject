"""Einmaliges Migrationsskript: kopiert die Bestandsdaten aus der alten MySQL-DB
in die neue PostgreSQL-DB, inkl. der ursprünglichen IDs (Fremdschlüssel wie
jobs.customer_id/resumes.user_id müssen erhalten bleiben).

Voraussetzungen:
- Die alte MySQL-DB läuft noch und ist erreichbar (Verbindungsdaten unten).
- pymysql ist lokal installiert (nicht mehr Teil von requirements.txt):
      pip install pymysql
- Die neue Postgres-DB ist erreichbar über die normalen DB_*-Werte aus .env.

Verbindungsdaten zur alten MySQL-DB werden aus separaten SRC_DB_*-Env-Vars
gelesen, damit sie nicht mit den (jetzt auf Postgres zeigenden) DB_*-Werten
kollidieren, z.B.:
    SRC_DB_HOST=127.0.0.1 SRC_DB_PORT=3310 SRC_DB_USER=root \\
    SRC_DB_PASSWORD=... SRC_DB_NAME=aiproject \\
    python migrate_mysql_to_postgres.py

Ausführung: docker compose exec app python migrate_mysql_to_postgres.py
(oder lokal, sofern beide DBs vom Host aus erreichbar sind).
"""
import json
import os

import pymysql
from dotenv import load_dotenv
from pymysql.cursors import DictCursor

import db

load_dotenv()

# Tabellen in Fremdschlüssel-Reihenfolge: jobs.customer_id -> customers,
# resumes.user_id -> users.
_TABLES = ["users", "customers", "jobs", "resumes"]


def _mysql_connection():
    return pymysql.connect(
        host=os.environ["SRC_DB_HOST"],
        port=int(os.environ["SRC_DB_PORT"]),
        user=os.environ["SRC_DB_USER"],
        password=os.environ["SRC_DB_PASSWORD"],
        database=os.environ["SRC_DB_NAME"],
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


def _copy_table(mysql_conn, pg_conn, table):
    with mysql_conn.cursor() as mysql_cur:
        mysql_cur.execute(f"SELECT * FROM {table}")
        rows = mysql_cur.fetchall()

    print(f"{table}: {len(rows)} Zeile(n) aus MySQL gelesen.")
    if not rows:
        return

    columns = list(rows[0].keys())
    column_list = ", ".join(columns)
    # MySQL JSON-Spalten kommen über pymysql als Text zurück - in Postgres
    # direkt als jsonb casten, damit der Zieltyp stimmt.
    value_placeholders = ", ".join("%s::jsonb" if c == "embedding" else "%s" for c in columns)

    with pg_conn.cursor() as pg_cur:
        for row in rows:
            values = [row[column] for column in columns]
            pg_cur.execute(
                f"INSERT INTO {table} ({column_list}) VALUES ({value_placeholders})",
                values,
            )
        # Sequence auf den höchsten übernommenen Wert setzen, damit künftige
        # SERIAL-Inserts nicht mit den übernommenen IDs kollidieren.
        pg_cur.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1))"
        )
    print(f"{table}: {len(rows)} Zeile(n) nach Postgres übernommen.")


if __name__ == "__main__":
    db.init_db()

    mysql_conn = _mysql_connection()
    pg_conn = db.get_connection()
    try:
        for table in _TABLES:
            _copy_table(mysql_conn, pg_conn, table)
    finally:
        mysql_conn.close()
        pg_conn.close()

    print("Migration abgeschlossen.")
