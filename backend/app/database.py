from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Convencion de nombres automatica para constraints (FKs, indices, etc.). Sin esto,
# SQLite no puede aplicar migraciones que agreguen/quiten una clave foranea, porque
# necesita un nombre explicito para poder recrear la tabla en modo batch.
convencion_nombres = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
Base = declarative_base(metadata=MetaData(naming_convention=convencion_nombres))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
