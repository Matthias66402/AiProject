from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text, func, select

from models.base import Base, get_session, to_dict


class CoverLetter(Base):
    """KI-erstelltes Motivationsschreiben einer Person für eine Stelle, siehe
    services/cover_letter_service.py. resume_id = Lebenslauf-Version, aus der
    es erstellt wurde."""
    __tablename__ = "cover_letters"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    deleted = Column(Boolean, nullable=False, default=False, server_default="false")


def create_cover_letter(user_id, job_id, resume_id, content):
    with get_session() as session:
        letter = CoverLetter(user_id=user_id, job_id=job_id, resume_id=resume_id, content=content)
        session.add(letter)
        session.flush()
        return letter.id


def get_cover_letter(letter_id):
    with get_session() as session:
        stmt = select(CoverLetter).where(CoverLetter.id == letter_id, CoverLetter.deleted.is_(False))
        return to_dict(session.scalars(stmt).first())


def list_cover_letters(user_id, job_id):
    """Eigene Motivationsschreiben zu einer Stelle, neueste zuerst."""
    with get_session() as session:
        stmt = (
            select(CoverLetter)
            .where(CoverLetter.user_id == user_id, CoverLetter.job_id == job_id, CoverLetter.deleted.is_(False))
            .order_by(CoverLetter.created_at.desc(), CoverLetter.id.desc())
        )
        return [to_dict(letter) for letter in session.scalars(stmt)]


def delete_cover_letter(letter_id):
    """Wie bei Lebensläufen nur deaktivieren (deleted=true)."""
    with get_session() as session:
        letter = session.get(CoverLetter, letter_id)
        if letter is not None:
            letter.deleted = True
