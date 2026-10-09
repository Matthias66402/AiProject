import csv
import os

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

from models.user import ROLES, DEFAULT_ROLE

# PLZ-Koordinaten (GeoNames, CC BY 4.0) für die Entfernungssuche der Stellenliste,
# siehe _load_zip_geo.
_ZIP_GEO_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plz_geo_de.csv")

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
    # KI-erzeugtes Matching-Profil, aus dem das Embedding berechnet wird
    # (services/match_profile_service.py).
    "match_profile": "TEXT",
}

_USER_COLUMNS = {
    "zip": "VARCHAR(10)",
    "city": "VARCHAR(100)",
}

_RESUME_COLUMNS = {
    "match_profile": "TEXT",
    "embedding": "vector(1536)",
    "deleted": "BOOLEAN NOT NULL DEFAULT FALSE",
    # Auf eine Stelle zugeschnittene Lebenslauf-Version (NULL = allgemeine Version),
    # siehe services/resume_tailoring_service.py.
    "target_job_id": "INT REFERENCES jobs(id)",
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


def _load_zip_geo(cur):
    """Legt die PLZ-Koordinaten-Tabelle an, befüllt sie einmalig aus
    db/plz_geo_de.csv und definiert die SQL-Funktionen für die Umkreissuche der
    Stellenliste: zip_distance_km() (Luftlinie per Haversine-Formel) und
    within_match_radius(job_zip, user_zip, radius_km). Letztere ist TRUE, wenn
    kein Umkreis gesetzt ist oder eine der beiden PLZ fehlt bzw. unbekannt ist -
    Einträge ohne verwertbaren Ort werden also nicht aussortiert."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS plz_geo (
            zip VARCHAR(5) PRIMARY KEY,
            lat DOUBLE PRECISION NOT NULL,
            lon DOUBLE PRECISION NOT NULL
        )
    """)
    cur.execute("SELECT EXISTS (SELECT 1 FROM plz_geo) AS filled")
    if not cur.fetchone()["filled"]:
        with open(_ZIP_GEO_CSV, encoding="utf-8") as f:
            rows = [(row["zip"], float(row["lat"]), float(row["lon"]))
                    for row in csv.DictReader(line for line in f if not line.startswith("#"))]
        execute_values(cur, "INSERT INTO plz_geo (zip, lat, lon) VALUES %s", rows)

    cur.execute("""
        CREATE OR REPLACE FUNCTION zip_distance_km(a TEXT, b TEXT) RETURNS DOUBLE PRECISION
        LANGUAGE sql STABLE AS $$
            SELECT 6371 * 2 * asin(sqrt(
                power(sin(radians(g2.lat - g1.lat) / 2), 2)
                + cos(radians(g1.lat)) * cos(radians(g2.lat)) * power(sin(radians(g2.lon - g1.lon) / 2), 2)
            ))
            FROM plz_geo g1, plz_geo g2
            WHERE g1.zip = trim(a) AND g2.zip = trim(b)
        $$
    """)
    cur.execute("""
        CREATE OR REPLACE FUNCTION within_match_radius(job_zip TEXT, user_zip TEXT, radius_km INT) RETURNS BOOLEAN
        LANGUAGE sql STABLE AS $$
            SELECT radius_km IS NULL OR COALESCE(zip_distance_km(job_zip, user_zip) <= radius_km, TRUE)
        $$
    """)


def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            _load_zip_geo(cur)

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

            # Umkreis pro Nutzer (Stand 2026-10-09 kurzzeitig im Profil) ist durch
            # die Entfernungs-Auswahl der Stellensuche ersetzt.
            cur.execute("ALTER TABLE users DROP COLUMN IF EXISTS match_radius_km")

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
