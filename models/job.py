from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, delete, func, select

from models.base import Base, MIN_MATCH_SIMILARITY, escape_like, get_session, to_dict
from models.customer import Customer


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
    embedding = Column(Vector(1536))


def _position_search_filter(search):
    """ILIKE-Filter fürs Suchfeld in der React-Stellenangebote-Liste - sucht
    (noch) nur in der Position."""
    return Job.position.ilike(f"%{escape_like(search)}%", escape="\\")


def list_jobs(customer_id=None, limit=None, offset=None, search=None):
    with get_session() as session:
        stmt = select(Job, Customer.company_name.label("customer_name")).join(Customer, Customer.id == Job.customer_id)
        if customer_id:
            stmt = stmt.where(Job.customer_id == customer_id)
        if search:
            stmt = stmt.where(_position_search_filter(search))
        stmt = stmt.order_by(Job.created_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset or 0)
        result = []
        for row in session.execute(stmt).all():
            job = to_dict(row.Job)
            job["customer_name"] = row.customer_name
            result.append(job)
        return result


def count_jobs(customer_id=None, search=None):
    with get_session() as session:
        stmt = select(func.count()).select_from(Job)
        if customer_id:
            stmt = stmt.where(Job.customer_id == customer_id)
        if search:
            stmt = stmt.where(_position_search_filter(search))
        return session.scalar(stmt)


def get_job(job_id):
    with get_session() as session:
        stmt = select(Job, Customer.company_name.label("customer_name")).join(Customer, Customer.id == Job.customer_id).where(Job.id == job_id)
        row = session.execute(stmt).first()
        if row is None:
            return None
        job = to_dict(row.Job)
        job["customer_name"] = row.customer_name
        return job


def create_job(position, content, valid_from, valid_until, customer_id, document_link=None, zip_code=None, city=None, embedding=None):
    with get_session() as session:
        session.add(Job(
            position=position, content=content, valid_from=valid_from, valid_until=valid_until,
            customer_id=customer_id, document_link=document_link, zip=zip_code, city=city, embedding=embedding,
        ))


def update_job(job_id, position, content, valid_from, valid_until, customer_id, zip_code=None, city=None, embedding=None):
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
        job.embedding = embedding


def find_matching_jobs(embedding, top_k=5, min_similarity=MIN_MATCH_SIMILARITY):
    """Liefert die top_k Jobs mit Cosine Similarity >= min_similarity zum
    gegebenen Embedding (1.0 = identisch), absteigend sortiert, inkl.
    Kundenname für die Anzeige. embedding kann von einem Job oder einem
    Lebenslauf stammen - für Job<->Job- wie auch Resume->Job-Matching
    nutzbar. Läuft nativ per pgvector-Index (idx_jobs_embedding_hnsw)."""
    similarity = (1 - Job.embedding.cosine_distance(embedding)).label("similarity")
    with get_session() as session:
        stmt = (
            select(Job.id, Job.position, Job.city, Job.valid_from, Job.valid_until,
                   Customer.company_name.label("customer_name"), similarity)
            .join(Customer, Customer.id == Job.customer_id)
            .where(Job.embedding.isnot(None))
            .where(similarity >= min_similarity)
            .order_by(Job.embedding.cosine_distance(embedding))
            .limit(top_k)
        )
        return [dict(row) for row in session.execute(stmt).mappings().all()]


def delete_job(job_id):
    with get_session() as session:
        session.execute(delete(Job).where(Job.id == job_id))
