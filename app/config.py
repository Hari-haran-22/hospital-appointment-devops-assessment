import os
from pathlib import Path


def secret(name: str) -> str:
    path = os.getenv(f"{name}_FILE")
    if not path:
        raise RuntimeError(f"{name}_FILE must point to a mounted secret")
    value = Path(path).read_text(encoding="utf-8").strip()
    if len(value) < 32:
        raise RuntimeError(f"{name} must contain at least 32 characters")
    return value


DATABASE_PASSWORD = secret("DATABASE_PASSWORD")
PATIENT_ONE_TOKEN = secret("PATIENT_ONE_TOKEN")
PATIENT_TWO_TOKEN = secret("PATIENT_TWO_TOKEN")
STAFF_TOKEN = secret("STAFF_TOKEN")
DATABASE_HOST = os.getenv("DATABASE_HOST", "db")
DATABASE_NAME = os.getenv("DATABASE_NAME", "appointments")
DATABASE_USER = os.getenv("DATABASE_USER", "appointment_app")
APP_VERSION = os.getenv("APP_VERSION", "local")
