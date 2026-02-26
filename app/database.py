from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import inspect, text
from app.config import settings

Base = declarative_base()

engine = create_async_engine(
    settings.database_url,
    echo=settings.development_mode,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db():
    """Dependency for getting async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_run_migrations)


def _run_migrations(sync_conn):
    """Run lightweight schema migrations for SQLite deployments."""
    inspector = inspect(sync_conn)

    if "schedules" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("schedules")}
        if "site_name" not in columns:
            sync_conn.execute(text("ALTER TABLE schedules ADD COLUMN site_name VARCHAR(255)"))

    if "poe_schedules" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("poe_schedules")}

        if "site_name" not in columns:
            sync_conn.execute(text("ALTER TABLE poe_schedules ADD COLUMN site_name VARCHAR(255)"))

        if "poe_only" not in columns:
            sync_conn.execute(text("ALTER TABLE poe_schedules ADD COLUMN poe_only BOOLEAN DEFAULT 1"))

        if "off_duration" not in columns:
            sync_conn.execute(text("ALTER TABLE poe_schedules ADD COLUMN off_duration INTEGER DEFAULT 15"))

            if "power_off_duration" in columns:
                sync_conn.execute(
                    text(
                        "UPDATE poe_schedules "
                        "SET off_duration = COALESCE(power_off_duration, 15) "
                        "WHERE off_duration IS NULL OR off_duration = 15"
                    )
                )
