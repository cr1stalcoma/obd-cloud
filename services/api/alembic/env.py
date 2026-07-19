import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def migration_url() -> str:
    """Always use POSTGRES_* from env_file — never stale DATABASE_URL (often user postgres)."""
    user = os.environ.get("POSTGRES_USER") or "obd"
    password = os.environ.get("POSTGRES_PASSWORD") or ""
    db = os.environ.get("POSTGRES_DB") or "obd_cloud"
    host = os.environ.get("POSTGRES_HOST") or "postgres"

    if not password:
        raise RuntimeError(
            "POSTGRES_PASSWORD missing in api container. "
            "Set it in ~/obd-cloud/.env and remove any DATABASE_URL= line from .env."
        )

    return f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}@{host}:5432/{db}"


config.set_main_option("sqlalchemy.url", migration_url())


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
