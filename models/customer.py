from sqlalchemy import Boolean, Column, DateTime, Integer, String, func, or_, select

from models.base import Base, escape_like, get_session, to_dict


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    company_name = Column(String(255), nullable=False)
    street = Column(String(255), nullable=False)
    street_number = Column(String(20), nullable=False)
    zip = Column(String(10), nullable=False)
    city = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    deleted = Column(Boolean, nullable=False, default=False, server_default="false")


def _search_filter(search):
    """ILIKE-Filter fürs Suchfeld in der React-Kunden-Liste - sucht über
    Firmierung, PLZ und Ort (jeweils ein Treffer reicht)."""
    pattern = f"%{escape_like(search)}%"
    return or_(
        Customer.company_name.ilike(pattern, escape="\\"),
        Customer.zip.ilike(pattern, escape="\\"),
        Customer.city.ilike(pattern, escape="\\"),
    )


def list_customers(limit=None, offset=None, search=None):
    with get_session() as session:
        stmt = select(Customer).where(Customer.deleted.is_(False)).order_by(Customer.company_name)
        if search:
            stmt = stmt.where(_search_filter(search))
        if limit is not None:
            stmt = stmt.limit(limit).offset(offset or 0)
        return [to_dict(c) for c in session.scalars(stmt).all()]


def count_customers(search=None):
    with get_session() as session:
        stmt = select(func.count()).select_from(Customer).where(Customer.deleted.is_(False))
        if search:
            stmt = stmt.where(_search_filter(search))
        return session.scalar(stmt)


def get_customer(customer_id):
    with get_session() as session:
        stmt = select(Customer).where(Customer.id == customer_id, Customer.deleted.is_(False))
        return to_dict(session.scalars(stmt).first())


def create_customer(company_name, street, street_number, zip_code, city):
    with get_session() as session:
        session.add(Customer(company_name=company_name, street=street, street_number=street_number, zip=zip_code, city=city))


def update_customer(customer_id, company_name, street, street_number, zip_code, city):
    with get_session() as session:
        customer = session.get(Customer, customer_id)
        if customer is None:
            return
        customer.company_name = company_name
        customer.street = street
        customer.street_number = street_number
        customer.zip = zip_code
        customer.city = city


def delete_customer(customer_id):
    """"Löschen" deaktiviert den Stellenanbieter nur noch (deleted=true) statt
    die Zeile zu entfernen - list_customers/get_customer blenden ihn dadurch
    überall aus, ohne dass bestehende jobs.customer_id-Referenzen brechen."""
    with get_session() as session:
        customer = session.get(Customer, customer_id)
        if customer is not None:
            customer.deleted = True
