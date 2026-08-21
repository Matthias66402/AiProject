import os

import pymysql
from pymysql.cursors import DictCursor

# Erlaubte Werte für users.role (MySQL SET-Spalte). Weitere Rollen können hier
# einfach ergänzt werden; die Spaltendefinition wird bei jedem Start abgeglichen.
ROLES = ["user", "admin"]
DEFAULT_ROLE = "user"
_ROLE_COLUMN_TYPE = "SET(" + ",".join(f"'{role}'" for role in ROLES) + ")"


def get_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        cursorclass=DictCursor,
        autocommit=True,
    )


def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    short_name VARCHAR(50) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role {_ROLE_COLUMN_TYPE} NOT NULL DEFAULT '{DEFAULT_ROLE}',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            # Migration für Tabellen, die vor Einführung von "role" angelegt wurden,
            # bzw. wenn ROLES sich seither geändert hat (z.B. VARCHAR -> SET, neue Rolle).
            cur.execute("""
                SELECT COLUMN_TYPE AS column_type FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'role'
            """)
            row = cur.fetchone()
            if row is None:
                cur.execute(f"ALTER TABLE users ADD COLUMN role {_ROLE_COLUMN_TYPE} NOT NULL DEFAULT '{DEFAULT_ROLE}'")
            elif row["column_type"] != _ROLE_COLUMN_TYPE.lower():
                cur.execute(f"ALTER TABLE users MODIFY COLUMN role {_ROLE_COLUMN_TYPE} NOT NULL DEFAULT '{DEFAULT_ROLE}'")
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


def create_user(first_name, last_name, short_name, email, password_hash, role=DEFAULT_ROLE):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (first_name, last_name, short_name, email, password_hash, role)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (first_name, last_name, short_name, email, password_hash, role),
            )
    finally:
        conn.close()


def update_user(user_id, first_name, last_name, short_name, email, role, password_hash=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if password_hash:
                cur.execute(
                    """
                    UPDATE users
                    SET first_name = %s, last_name = %s, short_name = %s, email = %s, role = %s, password_hash = %s
                    WHERE id = %s
                    """,
                    (first_name, last_name, short_name, email, role, password_hash, user_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE users
                    SET first_name = %s, last_name = %s, short_name = %s, email = %s, role = %s
                    WHERE id = %s
                    """,
                    (first_name, last_name, short_name, email, role, user_id),
                )
    finally:
        conn.close()
