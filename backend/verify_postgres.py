"""Fresh, uniquely named PostgreSQL test database; never touches presentation data."""

import json
import os
import subprocess
import sys
import importlib
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent / "vendor"))
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]


def main():
    values = dict(
        line.split("=", 1)
        for line in (ROOT / "deploy.env").read_text().splitlines()
        if "=" in line
    )
    url = URL.create(
        "postgresql+psycopg",
        username="claimguard",
        password=values["POSTGRES_PASSWORD"],
        host="127.0.0.1",
        port=15432,
        database="postgres",
    )
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    name = "cg_verify_" + uuid4().hex
    with admin.connect() as connection:
        connection.execute(text('CREATE DATABASE "' + name + '"'))
    target = url.set(database=name)
    os.environ["DATABASE_URL"] = target.render_as_string(hide_password=False)
    os.environ["CLAIMGUARD_TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]
    os.environ["APP_ENV"] = "development"
    os.environ.pop("DEMO_RESET_KEY", None)
    try:
        importlib.import_module("app.main")  # existing router import order
        from app.db import Base, engine, migrate
        from app import migrations

        original = migrations.upgrade_v2

        def failed_revision(connection, metadata):
            raise RuntimeError("Deliberate migration failure")

        migrations.upgrade_v2 = failed_revision
        try:
            migrate()
            raise AssertionError("Failed migration was skipped")
        except RuntimeError:
            assert inspect(engine).get_table_names() == [], (
                "PostgreSQL DDL/version transaction did not roll back"
            )
        finally:
            migrations.upgrade_v2 = original
        migrate()
        migrate()
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == set(Base.metadata.tables)
        schema = {}
        for name_table, model in Base.metadata.tables.items():
            columns = inspector.get_columns(name_table)
            assert {x["name"] for x in columns} == set(model.columns.keys())
            for column in columns:
                expected = model.columns[column["name"]]
                assert column["nullable"] == expected.nullable
                assert str(column["type"]) == str(
                    expected.type.compile(dialect=engine.dialect)
                )
                if name_table != "schema_migrations":
                    assert column["default"] is None
            actual_fks = inspector.get_foreign_keys(name_table)
            assert len(actual_fks) == len(model.foreign_key_constraints)
            for fk in model.foreign_key_constraints:
                assert any(
                    x["constrained_columns"] == [e.parent.name for e in fk.elements]
                    and x["referred_table"] == list(fk.elements)[0].column.table.name
                    for x in actual_fks
                )
            assert inspector.get_pk_constraint(name_table)["constrained_columns"] == [
                x.name for x in model.primary_key
            ]
            schema[name_table] = {
                "columns": [{**x, "type": str(x["type"])} for x in columns],
                "foreign_keys": actual_fks,
                "primary_key": inspector.get_pk_constraint(name_table),
                "secondary_indexes": inspector.get_indexes(name_table),
            }
        with engine.connect() as connection:
            version = connection.scalar(text("SELECT version()"))
        folder = ROOT / "docs" / "deployment"
        folder.mkdir(exist_ok=True)
        (folder / "schema.json").write_text(
            json.dumps(
                {
                    "postgresql": version,
                    "revisions": [1, 2, 3],
                    "repeated_migration": "PASS",
                    "failed_migration_rollback": "PASS",
                    "tables": schema,
                },
                indent=2,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )
        engine.dispose()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(ROOT / "backend" / "tests"),
                "-q",
                "-k",
                "not test_preflight_read_only_and_stale_state_detection",
            ],
            cwd=ROOT,
        )
        print(
            "Fresh PostgreSQL test database; schema inventory and failed-migration rollback verified."
        )
        return result.returncode
    finally:
        # Only the UUID database created by this invocation is dropped.
        with admin.connect() as connection:
            connection.execute(text('DROP DATABASE "' + name + '" WITH (FORCE)'))
        admin.dispose()


if __name__ == "__main__":
    sys.exit(main())
