"""Open a connection to the local EduConnect database."""

import os

import psycopg
from psycopg.rows import dict_row

# Matches the user, password, and database in docker-compose.yml.
DEFAULT_URL = "postgresql://educonnect:educonnect@localhost:5432/educonnect"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def connect():
    """Open one connection. Each row comes back as a dictionary."""
    return psycopg.connect(database_url(), row_factory=dict_row)
