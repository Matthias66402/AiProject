from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func, or_, select

from models.base import Base, MIN_MATCH_SIMILARITY, get_session, to_dict
from models.user import User


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    document_link = Column(String(500))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    embedding = Column(Vector(1536))
    deleted = Column(Boolean, nullable=False, default=False, server_default="false")
    # Auf diese Stelle zugeschnittene Version (NULL = allgemeine Version). Zählt im
    # Matching nur für die Zielstelle, siehe find_matching_resumes.
    target_job_id = Column(Integer, ForeignKey("jobs.id"))


def create_resume(content, document_link, user_id, embedding=None, target_job_id=None):
    with get_session() as session:
        resume = Resume(content=content, document_link=document_link, user_id=user_id, embedding=embedding,
                        target_job_id=target_job_id)
        session.add(resume)
        session.flush()
        return resume.id


def get_resume(resume_id):
    with get_session() as session:
        stmt = select(Resume).where(Resume.id == resume_id, Resume.deleted.is_(False))
        return to_dict(session.scalars(stmt).first())


def list_resumes_for_user(user_id):
    """Alle Versionen eines Nutzers, neueste zuerst - bei zugeschnittenen
    Versionen inkl. target_job_position für die Beschriftung."""
    from models.job import Job  # models.job importiert dieses Modul selbst

    with get_session() as session:
        stmt = (
            select(Resume, Job.position.label("target_job_position"))
            .outerjoin(Job, Job.id == Resume.target_job_id)
            .where(Resume.user_id == user_id, Resume.deleted.is_(False))
            .order_by(Resume.created_at.desc())
        )
        result = []
        for row in session.execute(stmt).all():
            resume = to_dict(row.Resume)
            resume["target_job_position"] = row.target_job_position
            result.append(resume)
        return result


def delete_resume(resume_id):
    """"Löschen" deaktiviert den Lebenslauf nur noch (deleted=true) statt die
    Zeile zu entfernen - get_resume/list_resumes_for_user/find_matching_resumes
    blenden ihn dadurch überall aus."""
    with get_session() as session:
        resume = session.get(Resume, resume_id)
        if resume is not None:
            resume.deleted = True


def find_matching_resumes(embedding, top_k=5, min_similarity=MIN_MATCH_SIMILARITY, job_id=None):
    """Analog zu find_matching_jobs(), für resumes - inkl. Namen des
    zugehörigen Nutzers für die Anzeige. Pro Nutzer zählt nur die ähnlichste
    Lebenslauf-Version (DISTINCT ON user_id), sonst belegt eine Person mit
    mehreren Versionen alle top_k-Plätze. Dadurch nutzt die Abfrage den
    HNSW-Index nicht mehr - für die aktuelle Datenmenge unkritisch.
    Auf eine Stelle zugeschnittene Versionen zählen nur, wenn job_id genau
    diese Stelle ist - sonst würden sie das Matching anderer Stellen verzerren."""
    distance = Resume.embedding.cosine_distance(embedding)
    with get_session() as session:
        best_per_user = (
            select(Resume.id, Resume.user_id, Resume.created_at, Resume.target_job_id,
                   (1 - distance).label("similarity"))
            .where(Resume.deleted.is_(False))
            .where(or_(Resume.target_job_id.is_(None), Resume.target_job_id == job_id))
            .where(Resume.embedding.isnot(None))
            .where(1 - distance >= min_similarity)
            .distinct(Resume.user_id)
            .order_by(Resume.user_id, distance)
            .subquery()
        )
        stmt = (
            select(best_per_user.c.id, best_per_user.c.user_id, best_per_user.c.created_at,
                   best_per_user.c.target_job_id,
                   User.first_name, User.last_name, User.short_name, best_per_user.c.similarity)
            .join(User, User.id == best_per_user.c.user_id)
            .order_by(best_per_user.c.similarity.desc())
            .limit(top_k)
        )
        return [dict(row) for row in session.execute(stmt).mappings().all()]
