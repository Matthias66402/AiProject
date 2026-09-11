import os

import psycopg2
from psycopg2.extras import RealDictCursor

from models.user import ROLES, DEFAULT_ROLE

_ROLE_CHECK_SQL = "role IN (" + ",".join(f"'{role}'" for role in ROLES) + ")"

_CUSTOMER_COLUMNS = {
    "company_name": "VARCHAR(255) NOT NULL",
    "street": "VARCHAR(255) NOT NULL",
    "street_number": "VARCHAR(20) NOT NULL",
    "zip": "VARCHAR(10) NOT NULL",
    "city": "VARCHAR(100) NOT NULL",
    "created_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    # "Löschen" deaktiviert seitdem nur noch (siehe delete_customer in
    # models/customer.py), statt die Zeile wirklich zu entfernen - u.a. damit
    # bestehende jobs.customer_id-Referenzen gültig bleiben.
    "deleted": "BOOLEAN NOT NULL DEFAULT FALSE",
}

_JOB_COLUMNS = {
    "document_link": "VARCHAR(500)",
    "zip": "VARCHAR(10)",
    "city": "VARCHAR(100)",
    "embedding": "vector(1536)",
    "deleted": "BOOLEAN NOT NULL DEFAULT FALSE",
}

_USER_COLUMNS = {
    "zip": "VARCHAR(10)",
    "city": "VARCHAR(100)",
}

_RESUME_COLUMNS = {
    "embedding": "vector(1536)",
    "deleted": "BOOLEAN NOT NULL DEFAULT FALSE",
}


def get_connection():
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dbname=os.environ["DB_NAME"],
        cursor_factory=RealDictCursor,
    )
    conn.autocommit = True
    return conn


def _migrate_embedding_to_vector(cur, table):
    """Wandelt eine noch als JSONB gespeicherte embedding-Spalte (Stand vor
    Einführung von pgvector) in-place in vector(1536) um. Idempotent - prüft
    den aktuellen Spaltentyp und tut bei bereits umgestellten Spalten nichts."""
    cur.execute("""
        SELECT udt_name FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = %s AND column_name = 'embedding'
    """, (table,))
    row = cur.fetchone()
    if row is not None and row["udt_name"] != "vector":
        cur.execute(f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector(1536) USING embedding::text::vector")


def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # Trigger-Funktion für "updated_at" (Postgres kennt kein
            # ON UPDATE CURRENT_TIMESTAMP wie MySQL) - einmal zentral definiert,
            # pro Tabelle mit updated_at-Spalte per Trigger registriert.
            cur.execute("""
                CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    short_name VARCHAR(50) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT '{DEFAULT_ROLE}',
                    zip VARCHAR(10),
                    city VARCHAR(100),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Rollen-Constraint bei jedem Start mit ROLES abgleichen (z.B. neue Rolle ergänzt).
            cur.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check")
            cur.execute(f"ALTER TABLE users ADD CONSTRAINT users_role_check CHECK ({_ROLE_CHECK_SQL})")
            cur.execute("DROP TRIGGER IF EXISTS trg_users_updated_at ON users")
            cur.execute("""
                CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
                FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """)

            # document_link auf users war ein Relikt aus der Zeit vor der resumes-Tabelle
            # (einzelner "letzter Lebenslauf" direkt am Nutzer) - inzwischen unbenutzt,
            # da resumes mehrere Lebensläufe pro Nutzer sauber über user_id abbildet.
            cur.execute("ALTER TABLE users DROP COLUMN IF EXISTS document_link")

            # Migration für users-Tabellen, die vor Einführung von zip/city angelegt wurden.
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'users'
            """)
            existing_user_columns = {row["column_name"] for row in cur.fetchall()}
            for column, definition in _USER_COLUMNS.items():
                if column not in existing_user_columns:
                    cur.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")

            # customer_id in jobs referenziert diese Tabelle, daher muss sie vorher existieren.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id SERIAL PRIMARY KEY,
                    company_name VARCHAR(255) NOT NULL,
                    street VARCHAR(255) NOT NULL,
                    street_number VARCHAR(20) NOT NULL,
                    zip VARCHAR(10) NOT NULL,
                    city VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("DROP TRIGGER IF EXISTS trg_customers_updated_at ON customers")
            cur.execute("""
                CREATE TRIGGER trg_customers_updated_at BEFORE UPDATE ON customers
                FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """)
            # Migration für customers-Tabellen, die noch als reiner id-Platzhalter angelegt wurden.
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'customers'
            """)
            existing_customer_columns = {row["column_name"] for row in cur.fetchall()}
            for column, definition in _CUSTOMER_COLUMNS.items():
                if column not in existing_customer_columns:
                    cur.execute(f"ALTER TABLE customers ADD COLUMN {column} {definition}")

            # customer_id in users referenziert customers (Zuordnung für Rolle 'customer',
            # bei anderen Rollen NULL) - separat migriert statt über _USER_COLUMNS, da
            # customers erst hier existiert.
            if "customer_id" not in existing_user_columns:
                cur.execute("ALTER TABLE users ADD COLUMN customer_id INT REFERENCES customers(id)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id SERIAL PRIMARY KEY,
                    position VARCHAR(300) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    valid_from DATE,
                    valid_until DATE,
                    customer_id INT NOT NULL,
                    document_link VARCHAR(500),
                    zip VARCHAR(10),
                    city VARCHAR(100),
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                )
            """)
            # Migration für jobs-Tabellen, die vor Einführung von document_link/zip/city angelegt wurden.
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'jobs'
            """)
            existing_job_columns = {row["column_name"] for row in cur.fetchall()}
            for column, definition in _JOB_COLUMNS.items():
                if column not in existing_job_columns:
                    cur.execute(f"ALTER TABLE jobs ADD COLUMN {column} {definition}")
            _migrate_embedding_to_vector(cur, "jobs")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_embedding_hnsw ON jobs USING hnsw (embedding vector_cosine_ops)")

            # user_id in resumes referenziert die users-Tabelle, daher muss sie vorher existieren.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    document_link VARCHAR(500),
                    user_id INT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            # Migration für resumes-Tabellen, die vor Einführung von embedding angelegt wurden.
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'resumes'
            """)
            existing_resume_columns = {row["column_name"] for row in cur.fetchall()}
            for column, definition in _RESUME_COLUMNS.items():
                if column not in existing_resume_columns:
                    cur.execute(f"ALTER TABLE resumes ADD COLUMN {column} {definition}")
            _migrate_embedding_to_vector(cur, "resumes")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_resumes_embedding_hnsw ON resumes USING hnsw (embedding vector_cosine_ops)")
    finally:
        conn.close()
