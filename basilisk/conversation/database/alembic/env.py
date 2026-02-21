"""Alembic environment configuration for conversation database."""

from alembic import context

from basilisk.conversation.database.manager import ConversationDatabase
from basilisk.conversation.database.models import Base

target_metadata = Base.metadata


def run_migrations_offline():
	"""Run migrations in 'offline' mode."""
	url = context.config.get_main_option("sqlalchemy.url")
	context.configure(
		url=url,
		target_metadata=target_metadata,
		literal_binds=True,
		dialect_opts={"paramstyle": "named"},
	)

	with context.begin_transaction():
		context.run_migrations()


def run_migrations_online():
	"""Run migrations in 'online' mode."""
	db_path = ConversationDatabase.get_db_path()
	connectable = ConversationDatabase.get_db_engine(db_path)
	with connectable.connect() as connection:
		context.configure(
			connection=connection, target_metadata=target_metadata
		)

		with context.begin_transaction():
			context.run_migrations()


if context.is_offline_mode():
	run_migrations_offline()
else:
	run_migrations_online()
