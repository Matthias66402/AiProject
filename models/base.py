import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

# Ab dieser Cosine-Similarity gilt ein Match als relevant genug für die
# Anzeige - ohne Schwellwert würden bei fehlenden echten Treffern trotzdem die
# "am wenigsten unpassenden" Ergebnisse als Match erscheinen. Kalibriert auf
# die Embeddings der Matching-Profile (services/match_profile_service.py, Stand
# 2026-10-09, 240 Paare): fachlich passende Paare liegen meist bei 0.75-0.88,
# unpassende bei 0.51-0.70 (Median 0.61). 0.71 = knapp über dem höchsten
# unpassenden Paar (Empfehlung von eval_matching.py). Das gemeinsame
# Profil-Format hebt alle Werte gegenüber Rohtext-Embeddings an - nach
# Änderungen am Profil-Prompt daher mit eval_matching.py neu prüfen.
MIN_MATCH_SIMILARITY = 0.71

# Engine/Sessionmaker erst bei der ersten tatsächlichen Nutzung aufbauen
# (nicht beim Modul-Import) - so wie zuvor db.get_connection(): os.environ
# wird erst zur Laufzeit gelesen, nicht beim Import von "db"/"models", der
# z.B. in app.py vor dem load_dotenv()-Aufruf passiert.
_engine = None
_SessionLocal = None


def _get_sessionmaker():
    global _engine, _SessionLocal
    if _SessionLocal is None:
        url = (
            f"postgresql+psycopg2://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
            f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
        )
        _engine = create_engine(url)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _SessionLocal


@contextmanager
def get_session():
    session = _get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def escape_like(value):
    """Escaped %/_ (ILIKE-Wildcards) in einem Suchbegriff, damit sie als Literal
    statt als Wildcard behandelt werden, falls jemand sie in ein Suchfeld tippt.
    Verwendung: column.ilike(f"%{escape_like(value)}%", escape="\\")."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def to_dict(instance):
    """Wandelt eine ORM-Instanz in ein flaches dict aller Spalten um - Ersatz
    für die dict-artigen Zeilen, die app.py/Templates bisher von psycopg2s
    RealDictCursor bekamen. pgvector liefert embedding-Spalten als
    numpy-Array zurück; .tolist() macht daraus wieder eine normale Python-
    Liste (u.a. wichtig für Wahrheitswert-Prüfungen wie "if job['embedding']",
    die auf einem Array mit mehreren Elementen einen ValueError werfen würden)."""
    if instance is None:
        return None
    result = {}
    for column in instance.__mapper__.column_attrs:
        value = getattr(instance, column.key)
        if hasattr(value, "tolist"):
            value = value.tolist()
        result[column.key] = value
    return result
