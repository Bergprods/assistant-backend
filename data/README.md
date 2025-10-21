# Data layer

- SQLAlchemy Base, engine and session helpers live in `data/context/db.py`.
- All models live in `data/models/__init__.py`.

Use `get_async_engine()` and `get_session_maker()` for DB access.
