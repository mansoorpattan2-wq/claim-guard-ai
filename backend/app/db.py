import os
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, Text, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine import make_url
from .logging_config import event

ROOT = Path(__file__).resolve().parents[1]
database_url = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'claim guard.db'}")
if database_url.startswith(("postgres://", "postgresql://")):
    database_url = "postgresql+psycopg://" + database_url.split("://", 1)[1]
database_dialect = make_url(database_url).get_backend_name()
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    **(
        {"connect_args": {"check_same_thread": False}}
        if database_dialect == "sqlite"
        else {
            "pool_size": 5,
            "max_overflow": 5,
            "pool_timeout": 10,
            "connect_args": {"connect_timeout": 5},
        }
    ),
)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Organisation(Base):
    __tablename__ = "organisations"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class Claim(Base):
    __tablename__ = "claims"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False)
    patient = Column(String, nullable=False)
    hospital = Column(String, nullable=False)
    procedure = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    readiness = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    claim_id = Column(String, ForeignKey("claims.id"), nullable=False)
    kind = Column(String, nullable=False)
    title = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    hash = Column(String, nullable=False)
    data = Column(JSON, nullable=False)


class Finding(Base):
    __tablename__ = "findings"
    id = Column(String, primary_key=True)
    claim_id = Column(String, ForeignKey("claims.id"), nullable=False)
    rule = Column(String, nullable=False)
    title = Column(String, nullable=False)
    status = Column(String, nullable=False)
    data = Column(JSON, nullable=False)


class Task(Base):
    __tablename__ = "resolution_tasks"
    id = Column(String, primary_key=True)
    claim_id = Column(String, ForeignKey("claims.id"), nullable=False)
    finding_id = Column(String, ForeignKey("findings.id"), nullable=False)
    status = Column(String, nullable=False)
    data = Column(JSON, nullable=False)


class Audit(Base):
    __tablename__ = "audit_events"
    id = Column(String, primary_key=True)
    claim_id = Column(String, ForeignKey("claims.id"))
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False)
    timestamp = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    event = Column(String, nullable=False)
    data = Column(JSON, nullable=False)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(String, primary_key=True)
    claim_id = Column(String, ForeignKey("claims.id"), nullable=False)
    agent = Column(String, nullable=False)
    data = Column(JSON, nullable=False)


class HumanDecision(Base):
    __tablename__ = "human_decisions"
    id = Column(String, primary_key=True)
    finding_id = Column(String, ForeignKey("findings.id"), nullable=False)
    data = Column(JSON, nullable=False)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False)
    text = Column(Text, nullable=False)
    data = Column(JSON, nullable=False)


class Migration(Base):
    __tablename__ = "schema_migrations"
    version = Column(Integer, primary_key=True)


class Intake(Base):
    __tablename__ = "intakes"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False)
    claim_id = Column(String, ForeignKey("claims.id"))
    status = Column(String, nullable=False)
    data = Column(JSON, nullable=False)


class IntakeFile(Base):
    __tablename__ = "intake_files"
    id = Column(String, primary_key=True)
    intake_id = Column(String, ForeignKey("intakes.id"), nullable=False)
    kind = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    data = Column(JSON, nullable=False)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id = Column(String, primary_key=True)
    claim_id = Column(String, ForeignKey("claims.id"), nullable=False)
    status = Column(String, nullable=False)
    data = Column(JSON, nullable=False)


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False)
    title = Column(String, nullable=False)
    status = Column(String, nullable=False)
    data = Column(JSON, nullable=False)


class ProcedureHistory(Base):
    __tablename__ = "procedure_history"
    id = Column(String, primary_key=True)
    org_id = Column(String, ForeignKey("organisations.id"), nullable=False)
    claim_id = Column(String, ForeignKey("claims.id"), nullable=False)
    patient = Column(String, nullable=False)
    procedure = Column(String, nullable=False)
    service_date = Column(String, nullable=False)
    data = Column(JSON, nullable=False)


def migrate():
    from sqlalchemy import select
    from .migrations import upgrade_v1, upgrade_v2, upgrade_v3

    try:
        with engine.begin() as connection:
            if database_dialect == "postgresql":
                # Serialize migration invocations without a process-local assumption.
                from sqlalchemy import text

                connection.execute(text("SELECT pg_advisory_xact_lock(210021)"))
            Migration.__table__.create(connection, checkfirst=True)
            applied = set(connection.scalars(select(Migration.version)))
            for version, upgrade in enumerate(
                (upgrade_v1, upgrade_v2, upgrade_v3), start=1
            ):
                if version not in applied:
                    upgrade(connection, Base.metadata)
                    connection.execute(
                        Migration.__table__.insert().values(version=version)
                    )
                    event("migration_applied", version=version)
    except Exception as exc:
        event("migration_failed", error_type=type(exc).__name__)
        raise RuntimeError(
            "Migration failed; inspect database access/schema. No revision was skipped."
        ) from None
