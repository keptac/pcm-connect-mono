from sqlalchemy.orm import Session
from .db.session import engine
from .core.seed import seed_data
from .db.base import Base
from .services.user_lifecycle import run_user_lifecycle_maintenance


def init():
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        seed_data(db)
        run_user_lifecycle_maintenance(db)
