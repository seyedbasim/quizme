"""SQLAlchemy schema + engine for the Postgres Store adapter.

The hand-written Alembic migration ``0001_initial`` is the authority for what the
live database looks like; :mod:`quizme.adapters.db.schema` mirrors it as
SQLAlchemy Core ``Table`` objects for the adapter to query. Future schema changes
should update both (or move to autogenerate).
"""
