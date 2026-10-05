from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func, select

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


def create_resume(content, document_link, user_id, embedding=None):
    with get_session() as session:
        resume = Resume(content=content, document_link=document_link, user_id=user_id, embedding=embedding)
        session.add(resume)
        session.flush()
        return resume.id


def get_resume(resume_id):
    with get_session() as session:
        stmt = select(Resume).where(Resume.id == resume_id, Resume.deleted.is_(False))
        return to_dict(session.scalars(stmt).first())


def list_resumes_for_user(user_id):
    with get_session() as session:
        stmt = (
            select(Resume)
            .where(Resume.user_id == user_id, Resume.deleted.is_(False))
            .order_by(Resume.created_at.desc())
        )
        return [to_dict(r) for r in session.scalars(stmt).all()]


def delete_resume(resume_id):
    """"Löschen" deaktiviert den Lebenslauf nur noch (deleted=true) statt die
    Zeile zu entfernen - get_resume/list_resumes_for_user/find_matching_resumes
    blenden ihn dadurch überall aus."""
    with get_session() as session:
        resume = session.get(Resume, resume_id)
        if resume is not None:
            resume.deleted = True


def find_matching_resumes(embedding, top_k=5, min_similarity=MIN_MATCH_SIMILARITY):
    """Analog zu find_matching_jobs(), für resumes - inkl. Namen des
    zugehörigen Nutzers für die Anzeige. Pro Nutzer zählt nur die ähnlichste
    Lebenslauf-Version (DISTINCT ON user_id), sonst belegt eine Person mit
    mehreren Versionen alle top_k-Plätze. Dadurch nutzt die Abfrage den
    HNSW-Index nicht mehr - für die aktuelle Datenmenge unkritisch."""
    distance = Resume.embedding.cosine_distance(embedding)
    with get_session() as session:
        best_per_user = (
            select(Resume.id, Resume.user_id, Resume.created_at, (1 - distance).label("similarity"))
            .where(Resume.deleted.is_(False))
            .where(Resume.embedding.isnot(None))
            .where(1 - distance >= min_similarity)
            .distinct(Resume.user_id)
            .order_by(Resume.user_id, distance)
            .subquery()
        )
        stmt = (
            select(best_per_user.c.id, best_per_user.c.user_id, best_per_user.c.created_at,
                   User.first_name, User.last_name, User.short_name, best_per_user.c.similarity)
            .join(User, User.id == best_per_user.c.user_id)
            .order_by(best_per_user.c.similarity.desc())
            .limit(top_k)
        )
        return [dict(row) for row in session.execute(stmt).mappings().all()]
