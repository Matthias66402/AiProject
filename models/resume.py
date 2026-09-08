from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, delete, func, select

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


def create_resume(content, document_link, user_id, embedding=None):
    with get_session() as session:
        resume = Resume(content=content, document_link=document_link, user_id=user_id, embedding=embedding)
        session.add(resume)
        session.flush()
        return resume.id


def get_resume(resume_id):
    with get_session() as session:
        return to_dict(session.get(Resume, resume_id))


def list_resumes_for_user(user_id):
    with get_session() as session:
        stmt = select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc())
        return [to_dict(r) for r in session.scalars(stmt).all()]


def delete_resume(resume_id):
    with get_session() as session:
        session.execute(delete(Resume).where(Resume.id == resume_id))


def find_matching_resumes(embedding, top_k=5, min_similarity=MIN_MATCH_SIMILARITY):
    """Analog zu find_matching_jobs(), für resumes - inkl. Namen des
    zugehörigen Nutzers für die Anzeige."""
    similarity = (1 - Resume.embedding.cosine_distance(embedding)).label("similarity")
    with get_session() as session:
        stmt = (
            select(Resume.id, Resume.user_id, Resume.created_at,
                   User.first_name, User.last_name, User.short_name, similarity)
            .join(User, User.id == Resume.user_id)
            .where(Resume.embedding.isnot(None))
            .where(similarity >= min_similarity)
            .order_by(Resume.embedding.cosine_distance(embedding))
            .limit(top_k)
        )
        return [dict(row) for row in session.execute(stmt).mappings().all()]
