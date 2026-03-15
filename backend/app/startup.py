from sqlalchemy.orm import Session
from .db.session import engine
from .core.seed import seed_data
from .db.base import Base


def init():
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        seed_data(db)
