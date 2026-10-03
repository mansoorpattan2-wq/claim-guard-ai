"""Deployment configuration; never serialize secrets into API responses."""

import os

APP_ENV = os.getenv("APP_ENV", "development")
ALLOWED_ORIGINS = [
    x.strip()
    for x in os.getenv(
        "ALLOWED_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000"
    ).split(",")
    if x.strip()
]


def validate():
    if "*" in ALLOWED_ORIGINS:
        raise RuntimeError("ALLOWED_ORIGINS must list explicit frontend origins.")
    if APP_ENV == "production":
        if not os.getenv("DATABASE_URL", "").startswith(("postgres",)):
            raise RuntimeError("Production requires a PostgreSQL DATABASE_URL.")
        if not os.getenv("ALLOWED_ORIGINS"):
            raise RuntimeError("Production requires explicit ALLOWED_ORIGINS.")
        if (
            os.getenv("DEMO_MODE", "true") == "true"
            and len(os.getenv("DEMO_RESET_KEY", "")) < 32
        ):
            raise RuntimeError(
                "Production demo requires a 32-character DEMO_RESET_KEY."
            )
