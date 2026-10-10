"""Prepare PostgreSQL: create the database (if missing) and the schema."""
import psycopg
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from psycopg import sql


class Command(BaseCommand):
    help = "Create the database and the schema if they do not exist."

    def handle(self, *args, **options):
        cfg = settings.DATABASES["default"]
        schema = settings.DATABASE_SCHEMA
        conn_kwargs = {
            "host": cfg["HOST"],
            "port": cfg["PORT"],
            "user": cfg["USER"],
            "password": cfg["PASSWORD"],
        }

        try:
            self._ensure_database(conn_kwargs, cfg["NAME"])
            with psycopg.connect(dbname=cfg["NAME"], autocommit=True, **conn_kwargs) as conn:
                conn.execute(
                    sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
                )
                self.stdout.write(self.style.SUCCESS(f'Schema "{schema}" is ready.'))
        except psycopg.OperationalError as exc:
            raise CommandError(f"Could not connect to PostgreSQL: {exc}") from exc

    def _ensure_database(self, conn_kwargs: dict, name: str) -> None:
        with psycopg.connect(dbname="postgres", autocommit=True, **conn_kwargs) as conn:
            exists = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
            ).fetchone()
            if exists:
                self.stdout.write(f'Database "{name}" already exists.')
                return
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            self.stdout.write(self.style.SUCCESS(f'Database "{name}" created.'))
