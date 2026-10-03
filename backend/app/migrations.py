"""Explicit initial schema revision. Future changes need new upgrade functions."""


def upgrade_v1(engine, metadata):
    """Create the P0 tables on a previously unmigrated database."""
    names = (
        "organisations",
        "claims",
        "documents",
        "findings",
        "resolution_tasks",
        "audit_events",
        "agent_runs",
        "human_decisions",
        "knowledge_chunks",
    )
    metadata.create_all(engine, tables=[metadata.tables[name] for name in names])


def upgrade_v2(engine, metadata):
    """Add P1 intake, upload, persisted-job and governed-source tables."""
    for name in ("intakes", "intake_files", "analysis_jobs", "knowledge_sources"):
        metadata.tables[name].create(engine, checkfirst=True)


def upgrade_v3(engine, metadata):
    """Add an explicitly synthetic prior-procedure registry for graph leads."""
    metadata.tables["procedure_history"].create(engine, checkfirst=True)
