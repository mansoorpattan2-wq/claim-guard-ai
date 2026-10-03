# Schema revisions

Revision **1** is implemented by `app/migrations.py:upgrade_v1` and applied by
`app/db.py:migrate`. The revision creates the declared P0 relational tables
through SQLAlchemy's dialect-specific DDL and records its version in
`schema_migrations`. Repeated execution is idempotent.

`python backend/manage.py migrate` is the entry point. Future revisions must
have explicit upgrade functions and version records; `create_all` is only an
initial-schema operation and cannot migrate altered columns.
