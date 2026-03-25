import os
import asyncio
from logging.config import fileConfig
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine
from alembic import context

from app.core.database import Base
import app.models

load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata # Remplacer 'None' par 'Base.metadata' une fois tes imports faits


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# [NOUVEAU] Fonction intermédiaire pour exécuter les migrations dans le contexte async
def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


# [MODIFIÉ] La fonction online est maintenant asynchrone
async def run_async_migrations() -> None:
    """In this scenario we need to create an AsyncEngine..."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # [MODIFIÉ] On lance la boucle asynchrone pour Alembic
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()