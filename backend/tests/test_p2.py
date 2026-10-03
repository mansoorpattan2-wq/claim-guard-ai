import copy
from app.db import Session, Migration


def test_connected_graph_and_real_signal_values(client, auth):
    g = client.get("/api/investigations/graph", headers=auth).json()
    assert g["status"] == "INVESTIGATION LEAD"
    assert {n["type"] for n in g["nodes"]} == {
        "Hospital",
        "Doctor",
        "Procedure",
        "Claim",
        "Document",
        "Invoice",
    }
    assert len([n for n in g["nodes"] if n["type"] == "Claim"]) == 6
    assert len([e for e in g["edges"] if e["target"] == "shared-document"]) == 6
    signals = {s["id"]: s for s in g["signals"]}
    assert signals["F03"]["observed"] == 6
    assert signals["F02-DEMO"]["observed"] == 15
    assert signals["F07"]["evidence"][0]["interval_days"] == 12
    assert signals["F08"]["evidence"]["peer_claim_count"] >= 44
    with Session() as s:
        assert s.get(Migration, 3)


def test_fhir_sample_import_and_mapping(client, auth):
    sample = client.get("/api/integrations/fhir/sample", headers=auth).json()
    assert sample["resourceType"] == "Bundle" and sample["type"] == "collection"
    result = client.post("/api/integrations/fhir/import", headers=auth, json=sample)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["mapping"]["patient"] == "SYN-FHIR-101"
    job = client.get("/api/analysis-jobs/" + data["id"], headers=auth).json()
    assert job["status"] == "COMPLETED"
    c = client.get("/api/claims/" + data["claim_id"], headers=auth).json()
    assert c["status"] == "READY" and c["amount"] == 78000 and len(c["documents"]) == 1
    assert any(
        e["event"] == "FHIR_BUNDLE_IMPORTED"
        for e in client.get("/api/audit?claim_id=" + c["id"], headers=auth).json()
    )


def test_fhir_rejects_unresolvable_references_and_mismatches(client, auth):
    sample = client.get("/api/integrations/fhir/sample", headers=auth).json()
    for field, value in [
        ("patient", {"reference": "https://untrusted.invalid/Patient/remote"}),
        ("total", {"value": 1, "currency": "INR"}),
        ("total", {"value": 78000, "currency": "USD"}),
    ]:
        bad = copy.deepcopy(sample)
        claim = next(
            e["resource"]
            for e in bad["entry"]
            if e["resource"]["resourceType"] == "Claim"
        )
        claim[field] = value
        assert (
            client.post(
                "/api/integrations/fhir/import", headers=auth, json=bad
            ).status_code
            == 422
        )
    bad = copy.deepcopy(sample)
    bad["entry"].append(copy.deepcopy(bad["entry"][0]))
    assert (
        client.post("/api/integrations/fhir/import", headers=auth, json=bad).status_code
        == 422
    )
    bad = copy.deepcopy(sample)
    bad["type"] = "transaction"
    assert (
        client.post("/api/integrations/fhir/import", headers=auth, json=bad).status_code
        == 422
    )


def test_integration_statuses_and_real_local_probes(client, auth):
    items = client.get("/api/integrations", headers=auth).json()
    assert (
        len(items) == 6
        and next(i for i in items if i["id"] == "nhcx")["status"] == "Not Connected"
    )
    for id in ["fhir", "storage"]:
        r = client.post(
            "/api/integrations/" + id + "/test", headers=auth, json={}
        ).json()
        assert r["status"] == "PASS" and r["external_connection"] is False
    assert (
        client.post("/api/integrations/nhcx/test", headers=auth, json={}).status_code
        == 422
    )


def test_complete_demo_reset_restores_four_stories_and_archives_intakes(client, auth):
    result = client.post("/api/demo/reset-all", headers=auth, json={})
    assert result.status_code == 200 and result.json()["restored_claims"] == 50
    assert len(client.get("/api/claims", headers=auth).json()) == 50
    expected = {
        "CG001": ("READY", 98),
        "CG021": ("NEEDS_RESOLUTION", 63),
        "CG030": ("HUMAN_REVIEW", 86),
        "CG048": ("INVESTIGATION", 95),
    }
    for id, (state, score) in expected.items():
        c = client.get("/api/claims/" + id, headers=auth).json()
        assert (c["status"], c["readiness"]) == (state, score)
    assert any(
        e["event"] == "DEMO_PRESENTATION_RESET"
        for e in client.get("/api/audit", headers=auth).json()
    )
    token = client.post("/api/session", json={"role": "Auditor"}).json()["token"]
    assert (
        client.post(
            "/api/demo/reset-all", headers={"Authorization": "Bearer " + token}, json={}
        ).status_code
        == 403
    )
    # Idempotent reset retains source and decision history.
    assert (
        client.post("/api/demo/reset-all", headers=auth, json={}).json()[
            "restored_claims"
        ]
        == 50
    )
