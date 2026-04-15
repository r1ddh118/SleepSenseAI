"""SQLAlchemy engine, session factory, Base, and get_db dependency."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

connect_args = {"check_same_thread": False} if "sqlite" in settings.database_url else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models_db import Prediction, Session, User  # noqa: F401

    Base.metadata.create_all(bind=engine)

    if "sqlite" in settings.database_url:
        with engine.begin() as conn:
            rows = conn.execute(text("PRAGMA table_info(predictions)")).fetchall()
            if rows:
                colnames = {r[1] for r in rows}
                if "recommendations_json" not in colnames:
                    conn.execute(
                        text("ALTER TABLE predictions ADD COLUMN recommendations_json TEXT")
                    )
