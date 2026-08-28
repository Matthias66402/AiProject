import os

import pymysql
from pymysql.cursors import DictCursor

# Erlaubte Werte für users.role (MySQL SET-Spalte). Weitere Rollen können hier
# einfach ergänzt werden; die Spaltendefinition wird bei jedem Start abgeglichen.
ROLES = ["user", "customer", "admin"]
DEFAULT_ROLE = "user"
_ROLE_COLUMN_TYPE = "SET(" + ",".join(f"'{role}'" for role in ROLES) + ")"

_CUSTOMER_COLUMNS = {
    "company_name": "VARCHAR(255) NOT NULL",
    "street": "VARCHAR(255) NOT NULL",
    "street_number": "VARCHAR(20) NOT NULL",
    "zip": "VARCHAR(10) NOT NULL",
    "city": "VARCHAR(100) NOT NULL",
    "created_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
}

_JOB_COLUMNS = {
    "document_link": "VARCHAR(500)",
    "zip": "VARCHAR(10)",
    "city": "VARCHAR(100)",
}


def get_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
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

            # customer_id in jobs referenziert diese Tabelle, daher muss sie vorher existieren.
            cur.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    company_name VARCHAR(255) NOT NULL,
                    street VARCHAR(255) NOT NULL,
                    street_number VARCHAR(20) NOT NULL,
                    zip VARCHAR(10) NOT NULL,
                    city VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            # Migration für customers-Tabellen, die noch als reiner id-Platzhalter angelegt wurden.
            cur.execute("""
                SELECT COLUMN_NAME AS column_name FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'customers'
            """)
            existing_customer_columns = {row["column_name"] for row in cur.fetchall()}
            for column, definition in _CUSTOMER_COLUMNS.items():
                if column not in existing_customer_columns:
                    cur.execute(f"ALTER TABLE customers ADD COLUMN {column} {definition}")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
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
                SELECT COLUMN_NAME AS column_name FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'jobs'
            """)
            existing_job_columns = {row["column_name"] for row in cur.fetchall()}
            for column, definition in _JOB_COLUMNS.items():
                if column not in existing_job_columns:
                    cur.execute(f"ALTER TABLE jobs ADD COLUMN {column} {definition}")
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


def list_customers():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM customers ORDER BY company_name")
            return cur.fetchall()
    finally:
        conn.close()


def list_jobs():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT jobs.*, customers.company_name AS customer_name
                FROM jobs
                JOIN customers ON customers.id = jobs.customer_id
                ORDER BY jobs.created_at DESC
            """)
            return cur.fetchall()
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


def create_job(position, content, valid_from, valid_until, customer_id, document_link=None, zip_code=None, city=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (position, content, valid_from, valid_until, customer_id, document_link, zip, city)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (position, content, valid_from, valid_until, customer_id, document_link, zip_code, city),
            )
    finally:
        conn.close()


def update_job(job_id, position, content, valid_from, valid_until, customer_id, zip_code=None, city=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET position = %s, content = %s, valid_from = %s, valid_until = %s, customer_id = %s, zip = %s, city = %s
                WHERE id = %s
                """,
                (position, content, valid_from, valid_until, customer_id, zip_code, city, job_id),
            )
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
