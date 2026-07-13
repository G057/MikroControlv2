from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import get_settings

settings = get_settings()

db_url = settings.DATABASE_URL

# PostgreSQL (and any server DB) connection tuning.
connect_args = {}
if db_url.startswith("postgresql"):
    # Client encoding / keepalive knobs can be added here if needed.
    pass

engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)

# Ensure session timezone matches DB expectations for timestamptz columns.
if db_url.startswith("postgresql"):
    @event.listens_for(engine, "connect")
    def _set_pg_session(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SET TIME ZONE 'UTC'")
        except Exception:
            pass
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
