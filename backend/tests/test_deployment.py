"""Deployment boundaries; same claim behavior on both supported databases."""

from app.main import TOKENS
from app.storage import storage
import pytest


def test_liveness_and_database_readiness_without_credentials(client):
    assert client.get("/health").status_code == 200
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["schema_version"] == 3
    assert set(response.json()) == {"status", "database", "schema_version"}
    assert "password" not in response.text.lower()


def test_reset_requires_deployment_secret_and_existing_role(client, auth, monkeypatch):
    monkeypatch.setenv("DEMO_RESET_KEY", "x" * 32)
    assert client.post("/api/demo/reset-all", headers=auth).status_code == 403
    bad = {**auth, "X-Demo-Reset-Key": "wrong"}
    assert client.post("/api/demo/reset", headers=bad).status_code == 403
    secret = {"X-Demo-Reset-Key": "x" * 32}
    assert client.post("/api/demo/reset-all", headers=secret).status_code == 401
    token = client.post("/api/session", json={"role": "Auditor"}).json()["token"]
    assert TOKENS[token]["role"] == "Auditor"
    assert (
        client.post(
            "/api/demo/reset-all",
            headers={**secret, "Authorization": "Bearer " + token},
        ).status_code
        == 403
    )
    assert (
        client.post("/api/demo/reset-all", headers={**auth, **secret}).status_code
        == 200
    )
    assert client.get("/api/claims/CG021", headers=auth).json()["readiness"] == 63


def test_explicit_cors_rejects_unlisted_browser_origin(client):
    response = client.options(
        "/api/claims",
        headers={
            "Origin": "https://unlisted.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_readiness_reports_failure_without_exception_details(client, monkeypatch):
    import app.main as main

    def unavailable():
        raise RuntimeError("postgresql://user:secret@host/private")

    monkeypatch.setattr(main, "Session", unavailable)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not ready", "reason": "Database unavailable."}
    assert "secret" not in response.text
    assert client.get("/health").status_code == 200


def test_storage_interface_rejects_paths_and_retains_opaque_bytes():
    for key in ["../outside", "a/b", "a\\b", "/absolute", ""]:
        with pytest.raises(ValueError):
            storage.put(key, b"synthetic")
    key = "deployment-test-probe"
    try:
        storage.put(key, b"synthetic upload")
        assert storage.get(key) == b"synthetic upload"
    finally:
        storage.delete(key)


def test_failed_commit_never_returns_success(client, auth, monkeypatch):
    from app.db import Session

    def fail_commit(self):
        raise RuntimeError("private database connection details")

    monkeypatch.setattr(Session.class_, "commit", fail_commit)
    response = client.post("/api/intakes", headers=auth)
    assert response.status_code == 500
    assert response.json() == {
        "detail": "Service unavailable. Retry or request manual review."
    }
    assert "private" not in response.text


def test_trace_order_uses_execution_time_not_database_row_order(client, auth):
    from app.db import Session, AgentRun

    with Session() as s:
        s.add(
            AgentRun(
                id="ORDER-LATER",
                claim_id="CG001",
                agent="Validating eligibility",
                data={"started_at": "2099-01-01T00:00:02+00:00", "status": "COMPLETED"},
            )
        )
        s.add(
            AgentRun(
                id="ORDER-EARLIER",
                claim_id="CG001",
                agent="Reading documents",
                data={"started_at": "2099-01-01T00:00:01+00:00", "status": "COMPLETED"},
            )
        )
        s.commit()
    runs = client.get("/api/claims/CG001", headers=auth).json()["runs"]
    assert [r["id"] for r in runs[-2:]] == ["ORDER-EARLIER", "ORDER-LATER"]
