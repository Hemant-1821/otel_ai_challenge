"""Shared database connection helper for all tools."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

import psycopg
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_DB_URL = "postgresql://hackathon:hackathon@localhost:5432/hotel_hackathon"


@contextmanager
def get_db() -> Generator[psycopg.Connection, None, None]:
    url = os.getenv("DATABASE_URL", _DEFAULT_DB_URL)
    with psycopg.connect(url) as conn:
        yield conn
