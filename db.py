import os

import psycopg2
from psycopg2.extras import RealDictCursor

from embeddings import to_vector_literal

# Erlaubte Werte für users.role. Weitere Rollen können hier einfach ergänzt
# werden; der CHECK-Constraint wird bei jedem Start abgeglichen.
ROLES = ["user", "customer", "admin"]
DEFAULT_ROLE = "user"
_ROLE_CHECK_SQL = "role IN (" + ",".join(f"'{role}'" for role in ROLES) + ")"

_CUSTOMER_COLUMNS = {
    "company_name": "VARCHAR(255) NOT NULL",
    "street": "VARCHAR(255) NOT NULL",
    "street_number": "VARCHAR(20) NOT NULL",
    "zip": "VARCHAR(10) NOT NULL",
    "city": "VARCHAR(100) NOT NULL",
    "created_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
}

_JOB_COLUMNS = {
    "document_link": "VARCHAR(500)",
    "zip": "VARCHAR(10)",
    "city": "VARCHAR(100)",
    "embedding": "vector(1536)",
}

_USER_COLUMNS = {
    "zip": "VARCHAR(10)",
    "city": "VARCHAR(100)",
}

_RESUME_COLUMNS = {
    "embedding": "vector(1536)",
}

# Ab dieser Cosine-Similarity gilt ein Match als relevant genug für die
# Anzeige. Erfahrungswert: eng verwandte Stellen/Lebensläufe liegen bei
# 0.75+, thematisch unverwandte Kombinationen bleiben meist unter 0.6 -
# ohne Schwellwert würden bei fehlenden echten Treffern trotzdem die
# "am wenigsten unpassenden" Ergebnisse als Match erscheinen.
MIN_MATCH_SIMILARITY = 0.60


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


def list_users():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users ORDER BY last_name, first_name")
            return cur.fetchall()
    finally:
        conn.close()


def get_user(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return cur.fetchone()
    finally:
        conn.close()


def list_customers(limit=None, offset=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            query = "SELECT * FROM customers ORDER BY company_name"
            params = []
            if limit is not None:
                query += " LIMIT %s OFFSET %s"
                params.extend([limit, offset or 0])
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()


def count_customers():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM customers")
            return cur.fetchone()["n"]
    finally:
        conn.close()


def list_jobs(customer_id=None, limit=None, offset=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT jobs.*, customers.company_name AS customer_name
                FROM jobs
                JOIN customers ON customers.id = jobs.customer_id
            """
            params = []
            if customer_id:
                query += " WHERE jobs.customer_id = %s"
                params.append(customer_id)
            query += " ORDER BY jobs.created_at DESC"
            if limit is not None:
                query += " LIMIT %s OFFSET %s"
                params.extend([limit, offset or 0])
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()


def count_jobs(customer_id=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if customer_id:
                cur.execute("SELECT COUNT(*) AS n FROM jobs WHERE customer_id = %s", (customer_id,))
            else:
                cur.execute("SELECT COUNT(*) AS n FROM jobs")
            return cur.fetchone()["n"]
    finally:
        conn.close()


def get_customer(customer_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM customers WHERE id = %s", (customer_id,))
            return cur.fetchone()
    finally:
        conn.close()


def create_customer(company_name, street, street_number, zip_code, city):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO customers (company_name, street, street_number, zip, city)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (company_name, street, street_number, zip_code, city),
            )
    finally:
        conn.close()


def update_customer(customer_id, company_name, street, street_number, zip_code, city):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE customers
                SET company_name = %s, street = %s, street_number = %s, zip = %s, city = %s
                WHERE id = %s
                """,
                (company_name, street, street_number, zip_code, city, customer_id),
            )
    finally:
        conn.close()


def delete_customer(customer_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
    finally:
        conn.close()


def get_job(job_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT jobs.*, customers.company_name AS customer_name
                FROM jobs
                JOIN customers ON customers.id = jobs.customer_id
                WHERE jobs.id = %s
            """, (job_id,))
            return cur.fetchone()
    finally:
        conn.close()


def create_job(position, content, valid_from, valid_until, customer_id, document_link=None, zip_code=None, city=None, embedding=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (position, content, valid_from, valid_until, customer_id, document_link, zip, city, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                """,
                (position, content, valid_from, valid_until, customer_id, document_link, zip_code, city,
                 to_vector_literal(embedding) if embedding is not None else None),
            )
    finally:
        conn.close()


def update_job(job_id, position, content, valid_from, valid_until, customer_id, zip_code=None, city=None, embedding=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET position = %s, content = %s, valid_from = %s, valid_until = %s, customer_id = %s, zip = %s, city = %s, embedding = %s::vector
                WHERE id = %s
                """,
                (position, content, valid_from, valid_until, customer_id, zip_code, city,
                 to_vector_literal(embedding) if embedding is not None else None, job_id),
            )
    finally:
        conn.close()


def find_matching_jobs(embedding, top_k=5, min_similarity=MIN_MATCH_SIMILARITY):
    """Liefert die top_k Jobs mit Cosine Similarity >= min_similarity zum
    gegebenen Embedding (1.0 = identisch), absteigend sortiert, inkl.
    Kundenname für die Anzeige. embedding kann von einem Job oder einem
    Lebenslauf stammen - für Job<->Job- wie auch Resume->Job-Matching
    nutzbar. Erwartet ein pgvector-Text-Literal wie aus einer embedding-Spalte
    gelesen (z.B. job["embedding"]), keinen rohen Python-float-list (dafür
    embeddings.to_vector_literal() nutzen). Läuft nativ per pgvector-Index."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT jobs.id, jobs.position, jobs.city, jobs.valid_from, jobs.valid_until,
                       customers.company_name AS customer_name,
                       1 - (jobs.embedding <=> %s::vector) AS similarity
                FROM jobs
                JOIN customers ON customers.id = jobs.customer_id
                WHERE jobs.embedding IS NOT NULL
                  AND 1 - (jobs.embedding <=> %s::vector) >= %s
                ORDER BY jobs.embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding, embedding, min_similarity, embedding, top_k),
            )
            return cur.fetchall()
    finally:
        conn.close()


def delete_job(job_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            return cur.fetchone()
    finally:
        conn.close()


def create_user(first_name, last_name, short_name, email, password_hash, role=DEFAULT_ROLE, zip_code=None, city=None, customer_id=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (first_name, last_name, short_name, email, password_hash, role, zip, city, customer_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (first_name, last_name, short_name, email, password_hash, role, zip_code, city, customer_id),
            )
    finally:
        conn.close()


def update_user(user_id, first_name, last_name, short_name, email, role, password_hash=None, zip_code=None, city=None, customer_id=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if password_hash:
                cur.execute(
                    """
                    UPDATE users
                    SET first_name = %s, last_name = %s, short_name = %s, email = %s, role = %s, password_hash = %s, zip = %s, city = %s, customer_id = %s
                    WHERE id = %s
                    """,
                    (first_name, last_name, short_name, email, role, password_hash, zip_code, city, customer_id, user_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE users
                    SET first_name = %s, last_name = %s, short_name = %s, email = %s, role = %s, zip = %s, city = %s, customer_id = %s
                    WHERE id = %s
                    """,
                    (first_name, last_name, short_name, email, role, zip_code, city, customer_id, user_id),
                )
    finally:
        conn.close()


def create_resume(content, document_link, user_id, embedding=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resumes (content, document_link, user_id, embedding)
                VALUES (%s, %s, %s, %s::vector)
                RETURNING id
                """,
                (content, document_link, user_id, to_vector_literal(embedding) if embedding is not None else None),
            )
            return cur.fetchone()["id"]
    finally:
        conn.close()


def get_resume(resume_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resumes WHERE id = %s", (resume_id,))
            return cur.fetchone()
    finally:
        conn.close()


def list_resumes_for_user(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM resumes WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def delete_resume(resume_id):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM resumes WHERE id = %s", (resume_id,))
    finally:
        conn.close()


def find_matching_resumes(embedding, top_k=5, min_similarity=MIN_MATCH_SIMILARITY):
    """Analog zu find_matching_jobs(), für resumes - inkl. Namen des
    zugehörigen Nutzers für die Anzeige."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT resumes.id, resumes.user_id, resumes.created_at,
                       users.first_name, users.last_name, users.short_name,
                       1 - (resumes.embedding <=> %s::vector) AS similarity
                FROM resumes
                JOIN users ON users.id = resumes.user_id
                WHERE resumes.embedding IS NOT NULL
                  AND 1 - (resumes.embedding <=> %s::vector) >= %s
                ORDER BY resumes.embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding, embedding, min_similarity, embedding, top_k),
            )
            return cur.fetchall()
    finally:
        conn.close()
