from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func, select

from models.base import Base, get_session, to_dict

# Erlaubte Werte für users.role. Weitere Rollen können hier einfach ergänzt
# werden; der CHECK-Constraint (db/db_init.py) wird bei jedem Start abgeglichen.
ROLES = ["user", "customer", "admin"]
DEFAULT_ROLE = "user"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    short_name = Column(String(50), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    zip = Column(String(10))
    city = Column(String(100))
    customer_id = Column(Integer, ForeignKey("customers.id"))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())


def list_users():
    with get_session() as session:
        users = session.scalars(select(User).order_by(User.last_name, User.first_name)).all()
        return [to_dict(u) for u in users]


def get_user(user_id):
    with get_session() as session:
        return to_dict(session.get(User, user_id))


def get_user_by_email(email):
    with get_session() as session:
        return to_dict(session.scalar(select(User).where(User.email == email)))


def create_user(first_name, last_name, short_name, email, password_hash, role=DEFAULT_ROLE, zip_code=None, city=None, customer_id=None):
    with get_session() as session:
        session.add(User(
            first_name=first_name, last_name=last_name, short_name=short_name, email=email,
            password_hash=password_hash, role=role, zip=zip_code, city=city, customer_id=customer_id,
        ))


def update_user(user_id, first_name, last_name, short_name, email, role, password_hash=None, zip_code=None, city=None, customer_id=None):
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None:
            return
        user.first_name = first_name
        user.last_name = last_name
        user.short_name = short_name
        user.email = email
        user.role = role
        if password_hash:
            user.password_hash = password_hash
        user.zip = zip_code
        user.city = city
        user.customer_id = customer_id


def update_user_role(user_id, role, customer_id=None):
    """Nur Rolle (und die daran hängende Stellenanbieter-Zuordnung) ändern - für
    Admins, die fremde Nutzer bearbeiten; alle übrigen Felder bleiben unberührt."""
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None:
            return
        user.role = role
        user.customer_id = customer_id
