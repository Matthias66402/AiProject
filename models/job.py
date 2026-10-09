from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, and_, func, or_, select, tuple_
from sqlalchemy.orm import aliased

from models.base import Base, MIN_MATCH_SIMILARITY, escape_like, get_session, to_dict
from models.customer import Customer
from models.resume import Resume


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    position = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    valid_from = Column(Date)
    valid_until = Column(Date)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    document_link = Column(String(500))
    zip = Column(String(10))
    city = Column(String(100))
    match_profile = Column(Text)
    embedding = Column(Vector(1536))
    deleted = Column(Boolean, nullable=False, default=False, server_default="false")


def _position_search_filter(search):
    """ILIKE-Filter fürs Suchfeld in der React-Stellenangebote-Liste - sucht
    (noch) nur in der Position."""
    return Job.position.ilike(f"%{escape_like(search)}%", escape="\\")


def _match_filter(user_id=None, min_similarity=MIN_MATCH_SIMILARITY):
    """Nur Stellen, zu denen mindestens eine Lebenslauf-Version ab min_similarity
    passt - gleiche Regeln wie user_match_similarities/job_match_counts
    (zugeschnittene Versionen nur für ihre Zielstelle). Mit user_id nur dessen
    Lebensläufe und nur heute gültige Stellen
    (Filter 'Passende Stellenangebote', Rolle 'user'), ohne alle (Filter
    '... mit passenden Kandidat:innen', Rolle 'customer' - dort zählen auch
    abgelaufene eigene Stellen)."""
    matched = aliased(Job)
    similarity = 1 - matched.embedding.cosine_distance(Resume.embedding)
    resume_cond = and_(Resume.deleted.is_(False), Resume.embedding.isnot(None),
                       or_(Resume.target_job_id.is_(None), Resume.target_job_id == matched.id))
    if user_id is not None:
        resume_cond = and_(resume_cond, Resume.user_id == user_id)
    stmt = (
        select(matched.id)
        .join(Resume, resume_cond)
        .where(matched.embedding.isnot(None), similarity >= min_similarity)
    )
    if user_id is not None:
        stmt = stmt.where(_active_filter(matched))
    return Job.id.in_(stmt)


def _apply_list_filters(stmt, customer_id, search, matching_user_id, with_candidates, origin_zip, max_distance_km):
    if origin_zip and max_distance_km:
        # Umkreissuche: SQL-Funktion within_match_radius (db/db_init.py) -
        # Stellen ohne bzw. mit unbekannter PLZ bleiben in der Liste.
        stmt = stmt.where(func.within_match_radius(Job.zip, origin_zip, max_distance_km))
    if customer_id:
        stmt = stmt.where(Job.customer_id == customer_id)
    if search:
        stmt = stmt.where(_position_search_filter(search))
    if matching_user_id:
        stmt = stmt.where(_match_filter(matching_user_id))
    if with_candidates:
        stmt = stmt.where(_match_filter())
    return stmt


def list_jobs(customer_id=None, limit=None, offset=None, search=None, matching_user_id=None, with_candidates=False,
              origin_zip=None, max_distance_km=None):
    """origin_zip + max_distance_km: nur Stellen bis max_distance_km Luftlinie
    um origin_zip (Auswahl 'Entfernung' der Stellensuche, siehe api/jobs.py)."""
    with get_session() as session:
        stmt = (
            select(Job, Customer.company_name.label("customer_name"))
            .join(Customer, Customer.id == Job.customer_id)
            .where(Job.deleted.is_(False))
        )
        stmt = _apply_list_filters(stmt, customer_id, search, matching_user_id, with_candidates,
                                   origin_zip, max_distance_km)
        stmt = stmt.order_by(Job.created_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset or 0)
        result = []
        for row in session.execute(stmt).all():
            job = to_dict(row.Job)
            job["customer_name"] = row.customer_name
            result.append(job)
        return result


def count_jobs(customer_id=None, search=None, matching_user_id=None, with_candidates=False,
               origin_zip=None, max_distance_km=None):
    with get_session() as session:
        stmt = select(func.count()).select_from(Job).where(Job.deleted.is_(False))
        stmt = _apply_list_filters(stmt, customer_id, search, matching_user_id, with_candidates,
                                   origin_zip, max_distance_km)
        return session.scalar(stmt)


def _active_filter(job=Job):
    """Stelle ist heute gültig: kein Start in der Zukunft, kein Ende in der
    Vergangenheit (fehlende Daten gelten als unbegrenzt). job erlaubt einen
    Alias statt der Job-Klasse (siehe _match_filter)."""
    today = func.current_date()
    return and_(
        or_(job.valid_from.is_(None), job.valid_from <= today),
        or_(job.valid_until.is_(None), job.valid_until >= today),
    )


def count_active_jobs():
    """Anzahl der heute gültigen, nicht gelöschten Stellen (Zahlenkachel auf /jobs)."""
    with get_session() as session:
        stmt = select(func.count()).select_from(Job).where(Job.deleted.is_(False), _active_filter())
        return session.scalar(stmt)


def count_active_matches(customer_id=None, user_id=None, min_similarity=MIN_MATCH_SIMILARITY):
    """Anzahl der Paare (heute gültige Stelle, Person) mit Cosine Similarity
    >= min_similarity für mindestens eine Lebenslauf-Version der Person - gleiche
    Schwelle und gleiche "eine Person = ein Treffer"-Logik wie find_matching_resumes.
    customer_id beschränkt auf die Stellen eines Stellenanbieters, user_id auf die
    Lebensläufe einer Person (= Anzahl der zu ihr passenden gültigen Stellen).
    Läuft als Kreuzprodukt ohne Index-Nutzung; für die aktuelle Datenmenge
    unkritisch, bei vielen tausend Einträgen besser zwischenspeichern."""
    similarity = 1 - Job.embedding.cosine_distance(Resume.embedding)
    with get_session() as session:
        stmt = (
            select(func.count(func.distinct(tuple_(Job.id, Resume.user_id))))
            .select_from(Job)
            .join(Resume, and_(Resume.deleted.is_(False),
                               or_(Resume.target_job_id.is_(None), Resume.target_job_id == Job.id)))
            .where(Job.deleted.is_(False), _active_filter())
            .where(Job.embedding.isnot(None), Resume.embedding.isnot(None))
            .where(similarity >= min_similarity)
        )
        if customer_id:
            stmt = stmt.where(Job.customer_id == customer_id)
        if user_id:
            stmt = stmt.where(Resume.user_id == user_id)
        return session.scalar(stmt)


def get_job(job_id):
    with get_session() as session:
        stmt = (
            select(Job, Customer.company_name.label("customer_name"))
            .join(Customer, Customer.id == Job.customer_id)
            .where(Job.id == job_id, Job.deleted.is_(False))
        )
        row = session.execute(stmt).first()
        if row is None:
            return None
        job = to_dict(row.Job)
        job["customer_name"] = row.customer_name
        return job


def create_job(position, content, valid_from, valid_until, customer_id, document_link=None, zip_code=None, city=None,
               match_profile=None, embedding=None):
    with get_session() as session:
        session.add(Job(
            position=position, content=content, valid_from=valid_from, valid_until=valid_until,
            customer_id=customer_id, document_link=document_link, zip=zip_code, city=city,
            match_profile=match_profile, embedding=embedding,
        ))


def update_job(job_id, position, content, valid_from, valid_until, customer_id, zip_code=None, city=None,
               match_profile=None, embedding=None):
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        job.position = position
        job.content = content
        job.valid_from = valid_from
        job.valid_until = valid_until
        job.customer_id = customer_id
        job.zip = zip_code
        job.city = city
        job.match_profile = match_profile
        job.embedding = embedding


def find_matching_jobs(embedding, top_k=5, min_similarity=MIN_MATCH_SIMILARITY):
    """Liefert die top_k heute gültigen Jobs mit Cosine Similarity >=
    min_similarity zum gegebenen Embedding (1.0 = identisch), absteigend
    sortiert, inkl. Kundenname für die Anzeige. embedding kann von einem Job,
    einem Lebenslauf oder einer Frage (KI-Assistent) stammen. Läuft nativ per
    pgvector-Index (idx_jobs_embedding_hnsw)."""
    similarity = (1 - Job.embedding.cosine_distance(embedding)).label("similarity")
    with get_session() as session:
        stmt = (
            select(Job.id, Job.position, Job.city, Job.valid_from, Job.valid_until,
                   Customer.company_name.label("customer_name"), similarity)
            .join(Customer, Customer.id == Job.customer_id)
            .where(Job.deleted.is_(False), _active_filter())
            .where(Job.embedding.isnot(None))
            .where(similarity >= min_similarity)
            .order_by(Job.embedding.cosine_distance(embedding))
            .limit(top_k)
        )
        return [dict(row) for row in session.execute(stmt).mappings().all()]


def user_match_similarities(user_id, job_ids, min_similarity=MIN_MATCH_SIMILARITY):
    """Für die Stellen-Liste der Rolle 'user': beste Cosine Similarity der
    Lebenslauf-Versionen von user_id je Stelle aus job_ids, nur Stellen ab
    min_similarity - als dict {job_id: similarity}. Zugeschnittene Versionen
    zählen wie in find_matching_resumes nur für ihre Zielstelle; abgelaufene
    Stellen zählen nicht."""
    if not job_ids:
        return {}
    similarity = func.max(1 - Job.embedding.cosine_distance(Resume.embedding))
    with get_session() as session:
        stmt = (
            select(Job.id, similarity.label("similarity"))
            .join(Resume, and_(Resume.user_id == user_id, Resume.deleted.is_(False),
                               Resume.embedding.isnot(None),
                               or_(Resume.target_job_id.is_(None), Resume.target_job_id == Job.id)))
            .where(Job.id.in_(job_ids), Job.embedding.isnot(None), _active_filter())
            .group_by(Job.id)
            .having(similarity >= min_similarity)
        )
        return {row.id: float(row.similarity) for row in session.execute(stmt).all()}


def job_match_counts(job_ids, min_similarity=MIN_MATCH_SIMILARITY):
    """Für die Stellen-Liste der Rolle 'customer': Anzahl passender Personen je
    Stelle aus job_ids (mind. eine Lebenslauf-Version ab min_similarity) - als
    dict {job_id: count}, Stellen ohne Treffer fehlen. Gleiche Regeln wie
    find_matching_resumes: eine Person zählt einmal, zugeschnittene Versionen
    nur für ihre Zielstelle."""
    if not job_ids:
        return {}
    similarity = 1 - Job.embedding.cosine_distance(Resume.embedding)
    with get_session() as session:
        stmt = (
            select(Job.id, func.count(func.distinct(Resume.user_id)).label("matches"))
            .join(Resume, and_(Resume.deleted.is_(False), Resume.embedding.isnot(None),
                               or_(Resume.target_job_id.is_(None), Resume.target_job_id == Job.id)))
            .where(Job.id.in_(job_ids), Job.embedding.isnot(None))
            .where(similarity >= min_similarity)
            .group_by(Job.id)
        )
        return {row.id: row.matches for row in session.execute(stmt).all()}


def job_similarity(job_id, embedding):
    """Cosine Similarity zwischen genau einer Stelle und einem Embedding, ohne
    Schwellwert - für den Vorher/Nachher-Vergleich beim Zuschneiden eines
    Lebenslaufs und die Anzeige zugeschnittener Versionen. None, wenn die Stelle
    fehlt, gelöscht ist oder kein Embedding hat."""
    if embedding is None:
        return None
    with get_session() as session:
        stmt = (
            select((1 - Job.embedding.cosine_distance(embedding)).label("similarity"))
            .where(Job.id == job_id, Job.deleted.is_(False), Job.embedding.isnot(None))
        )
        value = session.scalar(stmt)
        return float(value) if value is not None else None


def delete_job(job_id):
    """"Löschen" deaktiviert die Stelle nur noch (deleted=true) statt die Zeile
    zu entfernen - list_jobs/get_job/find_matching_jobs blenden sie dadurch
    überall aus, ohne dass z.B. bestehende Referenzen brechen."""
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is not None:
            job.deleted = True
