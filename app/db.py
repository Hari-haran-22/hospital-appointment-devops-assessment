from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app import config


@contextmanager
def connection():
    with psycopg.connect(
        host=config.DATABASE_HOST,
        dbname=config.DATABASE_NAME,
        user=config.DATABASE_USER,
        password=config.DATABASE_PASSWORD,
        connect_timeout=3,
        row_factory=dict_row,
    ) as conn:
        yield conn


def ready() -> bool:
    try:
        with connection() as conn:
            return (
                conn.execute("SELECT to_regclass('public.appointments') AS table_name").fetchone()[
                    "table_name"
                ]
                is not None
            )
    except psycopg.Error:
        return False
