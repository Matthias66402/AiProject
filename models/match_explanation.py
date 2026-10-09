from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from models.base import Base, get_session, to_dict


class MatchExplanation(Base):
    """Zwischengespeicherte KI-Begründung eines Treffers (Stelle x Lebenslauf-
    Version), siehe services/match_explanation_service.py."""
    __tablename__ = "match_explanations"

    job_id = Column(Integer, ForeignKey("jobs.id"), primary_key=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), primary_key=True)
    profiles_hash = Column(String(64), nullable=False)
    summary = Column(Text, nullable=False)
    matches = Column(JSONB, nullable=False)
    gaps = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())


def get_match_explanation(job_id, resume_id):
    with get_session() as session:
        return to_dict(session.get(MatchExplanation, (job_id, resume_id)))


def save_match_explanation(job_id, resume_id, profiles_hash, summary, matches, gaps):
    """Legt die Begründung an oder ersetzt eine veraltete (anderer profiles_hash)."""
    with get_session() as session:
        explanation = session.get(MatchExplanation, (job_id, resume_id))
        if explanation is None:
            explanation = MatchExplanation(job_id=job_id, resume_id=resume_id)
            session.add(explanation)
        explanation.profiles_hash = profiles_hash
        explanation.summary = summary
        explanation.matches = matches
        explanation.gaps = gaps
        explanation.created_at = func.current_timestamp()