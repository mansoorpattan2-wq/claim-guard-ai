from sqlalchemy import select, func
from app.db import Session, Audit, AgentRun, HumanDecision, Claim, Intake
from app.main import TOKENS
import io
import zipfile


def token(client, role):
    t = client.post("/api/session", json={"role": role}).json()["token"]
    return {"Authorization": "Bearer " + t}


def counts():
    with Session() as s:
        return tuple(
            s.scalar(select(func.count()).select_from(m))
            for m in [Claim, Intake, Audit, AgentRun, HumanDecision]
        )


def test_presentation_reset_clears_active_decisions_without_deleting_history(
    client, auth
):
    reviewer = token(client, "Medical Reviewer")
    assert (
        client.post(
            "/api/review/CG030-F04/decision",
            headers=reviewer,
            json={"decision": "OVERRIDE", "reason": "Reviewed demo package exception"},
        ).status_code
        == 200
    )
    assert client.get("/api/claims/CG030", headers=auth).json()["decisions"]
    assert client.post("/api/demo/reset-all", headers=auth).status_code == 200
    c = client.get("/api/claims/CG030", headers=auth).json()
    assert (c["status"], c["readiness"], c["decisions"]) == ("HUMAN_REVIEW", 86, [])
    assert len(c["runs"]) == 8
    active = client.get("/api/audit", headers=auth).json()
    assert len(active) == 1 and active[0]["event"] == "DEMO_PRESENTATION_RESET"
    history = client.get("/api/audit?include_history=true", headers=auth).json()
    assert len(history) > len(active)
    before = counts()
    assert client.post("/api/demo/reset-all", headers=auth).status_code == 200
    after = counts()
    assert after[3] == before[3] and after[4] == before[4]
    assert len(client.get("/api/audit", headers=auth).json()) == 1


def test_preflight_read_only_and_stale_state_detection(client, auth):
    client.post("/api/demo/reset-all", headers=auth)
    before = counts()
    check = client.get("/api/demo/preflight", headers=auth).json()
    assert (
        check["status"] == "DEMO READY"
        and check["database"] == "SQLite"
        and check["schema_version"] == 3
    )
    assert counts() == before
    with Session() as s:
        c = s.get(Claim, "CG021")
        c.readiness = 94
        s.commit()
    assert any(
        "CG021" in f
        for f in client.get("/api/demo/preflight", headers=auth).json()["failures"]
    )
    client.post("/api/demo/reset-all", headers=auth)


def test_malformed_resolution_and_duplicate_completion_remain_safe(client, auth):
    client.post("/api/demo/reset-all", headers=auth)
    assert (
        client.post("/api/resolutions/RT-CG021/complete", headers=auth).status_code
        == 409
    )
    for action in ["generate", "simulate_send"]:
        assert (
            client.post(
                "/api/resolutions/RT-CG021/request",
                headers=auth,
                json={"action": action},
            ).status_code
            == 200
        )
    assert (
        client.post(
            "/api/resolutions/RT-CG021/response",
            headers=auth,
            json={"text": "invalid evidence" * 4},
        ).status_code
        == 200
    )
    assert (
        client.post("/api/resolutions/RT-CG021/complete", headers=auth).status_code
        == 422
    )
    assert client.get("/api/claims/CG021", headers=auth).json()["readiness"] == 63
    # Restore the request state, then run and repeat the valid completion.
    client.post(
        "/api/resolutions/RT-CG021/request",
        headers=auth,
        json={"action": "simulate_send"},
    )
    client.post("/api/resolutions/RT-CG021/simulate-response", headers=auth)
    first = client.post("/api/resolutions/RT-CG021/complete", headers=auth).json()
    second = client.post("/api/resolutions/RT-CG021/complete", headers=auth).json()
    assert first["readiness"] == second["readiness"] == 94
    assert len(first["runs"]) == len(second["runs"]) and len(first["documents"]) == len(
        second["documents"]
    )
    client.post("/api/demo/reset-all", headers=auth)


def test_hardening_auth_bounds_and_archived_queues(client, auth):
    assert client.get("/api/demo/preflight").status_code == 401
    assert client.get("/api/audit?limit=99999", headers=auth).status_code == 422
    assert (
        client.post("/api/demo/reset-all", headers=token(client, "Auditor")).status_code
        == 403
    )
    TOKENS["hardening-other"] = {"role": "Auditor", "org_id": "other", "id": "other"}
    assert (
        client.get(
            "/api/investigations/graph",
            headers={"Authorization": "Bearer hardening-other"},
        ).json()["claims"]
        == []
    )
    with Session() as s:
        c = s.get(Claim, "CG036")
        c.data = {**c.data, "demo_archived": True}
        s.commit()
    assert not any(
        x["claim"]["id"] == "CG036"
        for x in client.get("/api/review", headers=auth).json()
    )
    with Session() as s:
        c = s.get(Claim, "CG036")
        c.data = {**c.data, "demo_archived": False}
        s.commit()


def test_safe_upload_basename_docx_parser_and_unsupported_type(client, auth):
    id = client.post("/api/intakes", headers=auth).json()["id"]
    result = client.post(
        f"/api/intakes/{id}/files",
        headers=auth,
        files={
            "files": (
                "../../evil.txt",
                b"SYNTHETIC FINAL BILL\nAmount: 78000",
                "text/plain",
            )
        },
    ).json()
    assert result["files"][0]["data"]["filename"] == "evil.txt"
    assert result["files"][0]["data"]["storage_key"].startswith("IF-")
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>SYNTHETIC OPERATIVE REPORT</w:t></w:r></w:p></w:body></w:document>',
        )
    result = client.post(
        f"/api/intakes/{id}/files",
        headers=auth,
        files={"files": ("source.docx", raw.getvalue(), "application/octet-stream")},
    )
    assert (
        result.status_code == 200
        and result.json()["files"][-1]["kind"] == "operative_report"
    )
    assert (
        client.post(
            f"/api/intakes/{id}/files",
            headers=auth,
            files={"files": ("source.exe", b"untrusted", "application/octet-stream")},
        ).status_code
        == 422
    )
