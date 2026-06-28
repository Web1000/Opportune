"""Shared SQLAlchemy database instance.

Kept in its own module so both app.py and models.py can import the same `db`
object without creating a circular import.
"""
from flask_sqlalchemy import SQLAlchemy

# Created here but not yet bound to an app; app.py calls db.init_app(app).
db = SQLAlchemy()
