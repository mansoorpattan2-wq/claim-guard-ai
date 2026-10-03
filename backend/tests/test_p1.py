from app.db import Session, Migration, AnalysisJob, Claim, AgentRun, Intake

TEXT = """SYNTHETIC OPERATIVE REPORT — DEMONSTRATION ONLY
Beneficiary: Demo Alias 101
Hospital: Cedar Demo Hospital
Procedure: Laparoscopic appendectomy
Admission: 2026-10-01
Discharge: 2026-10-03
Service date: 2026-10-02
Amount: 78000
Signed by: Dr. Demo
"""
IDENTITY = {
    "patient": "Demo Alias 101",
    "hospital": "Cedar Demo Hospital",
    "procedure": "Laparoscopic appendectomy",
    "admission": "2026-10-01",
    "discharge": "2026-10-03",
    "amount": 78000,
    "policy_active": True,
}


def intake(client, auth, text=TEXT, name="operative.txt"):
    id = client.post("/api/intakes", headers=auth, json={}).json()["id"]
    r = client.post(
        f"/api/intakes/{id}/files",
        headers=auth,
        files=[("files", (name, text.encode(), "text/plain"))],
    )
    assert r.status_code == 200, r.text
    return id, r.json()


def reviewer(client):
    token = client.post("/api/session", json={"role": "Medical Reviewer"}).json()[
        "token"
    ]
    return {"Authorization": "Bearer " + token}


def test_intake_and_analysis_trace(client, auth):
    id, preview = intake(client, auth)
    assert preview["files"][0]["kind"] == "operative_report"
    assert preview["identity"]["Beneficiary"] == "Demo Alias 101"
    job = client.post(f"/api/intakes/{id}/analyse", headers=auth, json=IDENTITY).json()
    result = client.get("/api/analysis-jobs/" + job["id"], headers=auth).json()
    assert result["status"] == "COMPLETED", result
    c = client.get("/api/claims/" + job["claim_id"], headers=auth).json()
    assert c["status"] == "READY" and c["readiness"] == 98
    assert len(result["data"]["steps"]) == 8
    for step in result["data"]["steps"]:
        assert {
            "started_at",
            "ended_at",
            "duration_ms",
            "inputs_summary",
            "tools",
            "evidence_refs",
            "finding_refs",
            "next_transition",
            "output",
        } <= step.keys()
        assert step["duration_ms"] >= 0
    assert len(c["runs"]) == 8
    assert (
        client.get(f"/api/intakes/{id}", headers=auth).json()["status"] == "COMPLETED"
    )
    assert (
        client.post(f"/api/intakes/{id}/analyse", headers=auth, json=IDENTITY).json()[
            "claim_id"
        ]
        == c["id"]
    )
    with Session() as s:
        assert s.get(Migration, 2) and s.get(AnalysisJob, job["id"])


def test_interrupted_job_recovery_and_retry(client, auth):
    from app.p1 import bootstrap

    id, _ = intake(client, auth)
    job = client.post(f"/api/intakes/{id}/analyse", headers=auth, json=IDENTITY).json()
    with Session() as s:
        old = s.get(AnalysisJob, job["id"])
        old.status = "RUNNING"
        s.add(
            AgentRun(
                id="INTERRUPTED-TEST",
                claim_id=job["claim_id"],
                agent="Reading documents",
                data={"status": "RUNNING", "job_id": job["id"]},
            )
        )
        s.commit()
        bootstrap(s)
        assert s.get(AnalysisJob, job["id"]).status == "FAILED"
        assert s.get(AgentRun, "INTERRUPTED-TEST").data["status"] == "FAILED"
        assert s.get(Intake, id).status == "FAILED"
        assert s.get(Claim, job["claim_id"]).status == "HUMAN_REVIEW"
    fresh = client.post(f"/api/analysis-jobs/{job['id']}/retry", headers=auth).json()
    assert fresh["id"] != job["id"]
    assert (
        client.get(f"/api/analysis-jobs/{fresh['id']}", headers=auth).json()["status"]
        == "COMPLETED"
    )
    assert (
        client.get(f"/api/intakes/{id}", headers=auth).json()["status"] == "COMPLETED"
    )


def test_document_classification_correction_and_validation(client, auth):
    id, p = intake(
        client, auth, TEXT.replace("OPERATIVE REPORT", "SOURCE"), name="source.txt"
    )
    assert p["files"][0]["kind"] == "unknown"
    fid = p["files"][0]["id"]
    corrected = client.post(
        f"/api/intakes/{id}/files/{fid}/classification",
        headers=auth,
        json={"kind": "operative_report"},
    ).json()
    assert corrected["files"][0]["kind"] == "operative_report"
    assert (
        client.post(
            f"/api/intakes/{id}/files/{fid}/classification",
            headers=auth,
            json={"kind": "made_up"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/intakes/{id}/files",
            headers=auth,
            files={"files": ("bad.pdf", b"not a PDF", "application/pdf")},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/intakes/{id}/files",
            headers=auth,
            files={"files": ("huge.txt", b"a" * 2000001, "text/plain")},
        ).status_code
        == 422
    )


def test_unreadable_intake_never_passes(client, auth):
    id = client.post("/api/intakes", headers=auth, json={}).json()["id"]
    r = client.post(
        f"/api/intakes/{id}/files",
        headers=auth,
        files={
            "files": (
                "scan.png",
                b"\x89PNG\r\n\x1a\n" + b"opaque test image",
                "image/png",
            )
        },
    )
    assert r.json()["files"][0]["data"]["extraction_status"] == "UNREADABLE"
    job = client.post(f"/api/intakes/{id}/analyse", headers=auth, json=IDENTITY).json()
    c = client.get("/api/claims/" + job["claim_id"], headers=auth).json()
    assert c["status"] == "HUMAN_REVIEW" and c["readiness"] <= 49
    assert any(f["rule"] == "EX01" for f in c["findings"])


def test_job_failure_and_retry_are_persisted(client, auth):
    id, _ = intake(client, auth)
    b = {**IDENTITY, "admission": "2027-01-01", "discharge": "2027-01-03"}
    job = client.post(f"/api/intakes/{id}/analyse", headers=auth, json=b).json()
    status = client.get("/api/analysis-jobs/" + job["id"], headers=auth).json()
    assert (
        status["status"] == "FAILED"
        and "Policy check unavailable" in status["data"]["error"]
    )
    c = client.get("/api/claims/" + job["claim_id"], headers=auth).json()
    assert c["status"] == "HUMAN_REVIEW"
    assert any(r["data"]["status"] == "FAILED" for r in c["runs"])
    retry = client.post(
        "/api/analysis-jobs/" + job["id"] + "/retry", headers=auth, json={}
    ).json()
    assert retry["id"] != job["id"] and retry["claim_id"] == job["claim_id"]


def test_intake_identity_conflicts_and_permissions(client, auth):
    id, _ = intake(client, auth, TEXT + "Beneficiary: Different Alias\n")
    job = client.post(f"/api/intakes/{id}/analyse", headers=auth, json=IDENTITY).json()
    c = client.get("/api/claims/" + job["claim_id"], headers=auth).json()
    assert c["data"]["identity_conflict"] and c["status"] == "HUMAN_REVIEW"
    token = client.post("/api/session", json={"role": "Auditor"}).json()["token"]
    assert (
        client.post(
            "/api/intakes", headers={"Authorization": "Bearer " + token}, json={}
        ).status_code
        == 403
    )


def test_review_override_requirement_and_recalculation(client, auth):
    h = reviewer(client)
    assert (
        client.post(
            "/api/review/CG030-F04/decision",
            headers=h,
            json={"decision": "OVERRIDE", "reason": " "},
        ).status_code
        == 422
    )
    result = client.post(
        "/api/review/CG030-F04/decision",
        headers=h,
        json={
            "decision": "OVERRIDE",
            "reason": "Synthetic package exception verified against source.",
        },
    ).json()
    assert result["status"] == "READY" and result["readiness"] == 98
    assert result["findings"][0]["status"] == "OVERRIDDEN"
    assert result["decisions"][-1]["data"]["original_finding"]["evidence"]
    rerun = client.post("/api/claims/CG030/analyse", headers=auth, json={}).json()
    assert rerun["status"] == "READY" and rerun["findings"][0]["status"] == "OVERRIDDEN"
    # Restore only this test's operational disposition; keep historical decisions.
    with Session() as s:
        from app.db import Finding
        from app.engine import analyse

        c = s.get(Claim, "CG030")
        f = s.get(Finding, "CG030-F04")
        f.data = {k: v for k, v in f.data.items() if not k.startswith("review")}
        f.status = "OPEN"
        analyse(s, c)
        s.commit()


def test_review_all_actions_are_audited(client, auth):
    h = reviewer(client)
    for d in ["AGREE", "REQUEST_INFORMATION", "ESCALATE"]:
        assert (
            client.post(
                "/api/review/CG031-F04/decision",
                headers=h,
                json={"decision": d, "reason": "Synthetic reviewer note"},
            ).status_code
            == 200
        )
    events = client.get("/api/audit?claim_id=CG031", headers=auth).json()
    assert {"REVIEW_AGREE", "REVIEW_REQUEST_INFORMATION", "REVIEW_ESCALATE"} <= {
        e["event"] for e in events
    }
    assert (
        client.post(
            "/api/review/CG031-F04/decision",
            headers=auth,
            json={"decision": "OVERRIDE", "reason": "No permission"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/review/CG021-F14/decision",
            headers=h,
            json={"decision": "OVERRIDE", "reason": "Cannot bypass evidence"},
        ).status_code
        == 422
    )


def test_knowledge_ranking_and_effective_dates(client, auth):
    catalog = client.get("/api/knowledge/catalog", headers=auth).json()
    assert next(x for x in catalog if x["status"] == "ACTIVE")["chunk_count"] == 4
    b = {
        "query": "Is anaesthesia separately billable for demo package LAP-APP-01?",
        "applicable_date": "2026-10-02",
    }
    result = client.post("/api/knowledge/retrieve", headers=auth, json=b).json()
    assert result["status"] == "GROUNDED" and "includes anaesthesia" in result["answer"]
    assert result["citations"] == ["PKG-6.1"] and result["passages"][0]["rank"] == 1
    assert {
        "score",
        "rank",
        "matched_terms",
        "authority",
        "page",
        "section",
        "version",
        "effective_date",
    } <= result["passages"][0].keys()
    unknown = client.post(
        "/api/knowledge/retrieve",
        headers=auth,
        json={**b, "applicable_date": "2025-10-02"},
    ).json()
    assert unknown["passages"] == [] and "INSUFFICIENT_EVIDENCE" in unknown["answer"]


def test_printable_passport_export(client, auth):
    r = client.get("/api/claims/CG021/printable", headers=auth)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert all(
        x in r.text
        for x in [
            "Claim Readiness Passport",
            "63%",
            "Unresolved issues",
            "Human decisions",
            "Document provenance",
            "DOC-4.2",
            "Generated",
        ]
    )
    with Session() as s:
        c = s.get(Claim, "CG001")
        c.patient = "<script>alert(1)</script>"
        s.commit()
    html = client.get("/api/claims/CG001/printable", headers=auth).text
    assert "&lt;script&gt;" in html and "<script>" not in html
    with Session() as s:
        c = s.get(Claim, "CG001")
        c.patient = "Beneficiary 001"
        s.commit()
