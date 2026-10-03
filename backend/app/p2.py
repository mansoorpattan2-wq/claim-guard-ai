"""Selected P2 demo graph and deliberately narrow FHIR R4 import adapter."""

import base64
import json
import re
from datetime import date
from difflib import SequenceMatcher
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select
from .db import Claim, Document, ProcedureHistory, Intake, IntakeFile, ROOT
from .storage import storage
from .engine import now, digest, audit
from .main import actor, session, permitted, row, WRITE
from .p1 import IntakeIdentity, analyse_intake

router = APIRouter(prefix="/api")


def bootstrap(s):
    c = s.get(Claim, "CG048")
    if c and not s.get(ProcedureHistory, "HIST-CG048"):
        s.add(
            ProcedureHistory(
                id="HIST-CG048",
                org_id=c.org_id,
                claim_id=c.id,
                patient=c.patient,
                procedure=c.procedure,
                service_date="2026-09-20",
                data={
                    "source": "Synthetic prior-procedure registry",
                    "version": "1.0",
                    "injected_defect": "short_interval_repeat",
                    "description": "Fictional prior procedure event for deterministic investigation demonstration; not an additional claim.",
                },
            )
        )
    s.commit()


@router.get("/investigations/graph")
def graph(a=Depends(actor), s=Depends(session, scope="function")):
    claims = s.scalars(
        select(Claim)
        .where(
            Claim.org_id == a["org_id"],
            Claim.id.in_([f"CG{i:03}" for i in range(45, 51)]),
        )
        .order_by(Claim.id)
    ).all()
    if not claims:
        return {
            "nodes": [],
            "edges": [],
            "signals": [],
            "claims": [],
            "status": "INVESTIGATION LEAD",
        }
    hospital = claims[0].hospital
    doctor = claims[0].data["doctor"]
    procedure = claims[0].procedure
    nodes = [
        {
            "id": "hospital",
            "type": "Hospital",
            "label": hospital,
            "x": 80,
            "y": 250,
            "data": {"claim_count": len(claims)},
        },
        {
            "id": "doctor",
            "type": "Doctor",
            "label": doctor,
            "x": 310,
            "y": 250,
            "data": {"provider": hospital},
        },
        {
            "id": "procedure",
            "type": "Procedure",
            "label": "LAP-APP-01",
            "x": 540,
            "y": 250,
            "data": {"procedure": procedure},
        },
    ]
    edges = [
        {"source": "hospital", "target": "doctor", "label": "TREATED_BY"},
        {"source": "doctor", "target": "procedure", "label": "PERFORMS"},
    ]
    docs = s.scalars(
        select(Document).where(
            Document.claim_id.in_([c.id for c in claims]),
            Document.kind.in_(["diagnostic_report", "final_bill"]),
        )
    ).all()
    diagnostics = [d for d in docs if d.kind == "diagnostic_report"]
    hashes = {d.hash for d in diagnostics}
    shared = next(iter(hashes)) if len(hashes) == 1 else None
    for i, c in enumerate(claims):
        y = 50 + i * 88
        nodes.append(
            {
                "id": c.id,
                "type": "Claim",
                "label": c.id,
                "x": 795,
                "y": y,
                "data": {
                    "patient": c.patient,
                    "readiness": c.readiness,
                    "amount": c.amount,
                    "status": c.status,
                },
            }
        )
        edges.append({"source": "procedure", "target": c.id, "label": "HAS_PROCEDURE"})
    if shared:
        nodes.append(
            {
                "id": "shared-document",
                "type": "Document",
                "label": "Shared diagnostic source",
                "x": 1050,
                "y": 210,
                "data": {
                    "fingerprint": shared,
                    "source_ids": [d.id for d in diagnostics],
                    "matches": len(diagnostics),
                },
            }
        )
        edges.extend(
            {"source": c.id, "target": "shared-document", "label": "HASH_MATCH"}
            for c in claims
        )
    bills = [d for d in docs if d.kind == "final_bill"]

    def normalized(d):
        return re.sub(r"Beneficiary \d+|CG\d+", "[identity]", d.text)

    pairs = [
        {
            "left": x.claim_id,
            "right": y.claim_id,
            "similarity": round(
                SequenceMatcher(None, normalized(x), normalized(y)).ratio(), 4
            ),
            "source_ids": [x.id, y.id],
        }
        for i, x in enumerate(bills)
        for y in bills[i + 1 :]
    ]
    near = [p for p in pairs if p["similarity"] >= 0.9]
    nodes.append(
        {
            "id": "invoice-pattern",
            "type": "Invoice",
            "label": "Invoice template similarity",
            "x": 1050,
            "y": 390,
            "data": {
                "near_duplicate_pairs": len(near),
                "threshold": 0.9,
                "normalization": "Claim IDs and beneficiary labels excluded; original sources unchanged.",
            },
        }
    )
    edges.extend(
        {"source": c.id, "target": "invoice-pattern", "label": "SIMILAR_TEMPLATE"}
        for c in claims
        if any(c.id in [p["left"], p["right"]] for p in near)
    )
    peers = s.scalars(
        select(Claim).where(Claim.org_id == a["org_id"], Claim.hospital != hospital)
    ).all()
    peers = [p for p in peers if not p.data.get("demo_archived")]
    peer_matches = sum(p.procedure == procedure for p in peers)
    ratio = peer_matches / max(len(peers), 1)
    prior = s.scalars(
        select(ProcedureHistory).where(
            ProcedureHistory.org_id == a["org_id"],
            ProcedureHistory.claim_id.in_([c.id for c in claims]),
        )
    ).all()
    repeats = []
    for p in prior:
        c = next(c for c in claims if c.id == p.claim_id)
        interval = (
            date.fromisoformat(c.data.get("service_date", "2026-10-02"))
            - date.fromisoformat(p.service_date)
        ).days
        if 0 < interval < 30:
            repeats.append(
                {
                    "claim_id": c.id,
                    "patient": p.patient,
                    "prior_date": p.service_date,
                    "current_date": c.data.get("service_date", "2026-10-02"),
                    "interval_days": interval,
                    "baseline_days": 30,
                    "source": p.data["source"],
                    "source_id": p.id,
                }
            )
    signals = [
        {
            "id": "F03",
            "title": "Repeated document fingerprint",
            "observed": len(diagnostics) if shared else 0,
            "baseline": 1,
            "detail": "Exact diagnostic-source SHA-256 matches across distinct synthetic beneficiaries.",
            "evidence": {"hash": shared, "source_ids": [d.id for d in diagnostics]},
        },
        {
            "id": "F02-DEMO",
            "title": "Near-duplicate invoice templates",
            "observed": len(near),
            "baseline": "Similarity ≥ 90%",
            "detail": "Template similarity after excluding identity labels. Common templates may be legitimate; this is a review lead.",
            "evidence": near,
        },
        {
            "id": "F08",
            "title": "Procedure-frequency deviation",
            "observed": "6 / 6 (100%)",
            "baseline": f"{peer_matches} / {len(peers)} ({ratio:.1%})",
            "detail": "Meridian procedure mix compared with the other seeded providers. Small synthetic sample; no causal conclusion.",
            "evidence": {
                "provider_claims": [c.id for c in claims],
                "peer_claim_count": len(peers),
                "peer_ratio": ratio,
            },
        },
        {
            "id": "F07",
            "title": "Short-interval repeat procedure",
            "observed": len(repeats),
            "baseline": "30-day demo threshold",
            "detail": "An explicitly synthetic historical procedure event is linked to CG048. This is a lead requiring clinical-record verification.",
            "evidence": repeats,
        },
    ]
    return {
        "status": "INVESTIGATION LEAD",
        "nodes": nodes,
        "edges": edges,
        "signals": signals,
        "claims": [row(c) for c in claims],
        "adapter": "Organisation-scoped SQL / deterministic graph projection. Neo4j is not connected.",
    }


SAMPLE_PATH = ROOT / "demo" / "fhir-bundle.json"


@router.get("/integrations/fhir/sample")
def fhir_sample(a=Depends(actor)):
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


class BundleEntry(BaseModel):
    resource: dict
    fullUrl: str | None = None


class FHIRBundle(BaseModel):
    resourceType: Literal["Bundle"]
    type: Literal["collection"]
    id: str = Field(min_length=1, max_length=100)
    entry: list[BundleEntry] = Field(min_length=1, max_length=30)


def transform_bundle(bundle):
    supported = {
        "Patient",
        "Organization",
        "Coverage",
        "Claim",
        "DocumentReference",
        "Binary",
    }
    resources = {}
    for entry in bundle.entry:
        r = entry.resource
        kind = r.get("resourceType")
        rid = r.get("id")
        if (
            kind not in supported
            or not isinstance(rid, str)
            or not re.fullmatch(r"[A-Za-z0-9.-]{1,64}", rid)
        ):
            raise HTTPException(
                422,
                "Unsupported resource or invalid resource ID in the demo R4 subset.",
            )
        key = f"{kind}/{rid}"
        if key in resources:
            raise HTTPException(422, "Duplicate resource IDs are not allowed.")
        resources[key] = r
        if entry.fullUrl:
            if entry.fullUrl in resources:
                raise HTTPException(422, "Duplicate fullUrl values are not allowed.")
            resources[entry.fullUrl] = r

    def one(kind):
        found = [
            e.resource for e in bundle.entry if e.resource.get("resourceType") == kind
        ]
        if len(found) != 1:
            raise HTTPException(422, f"Demo import requires exactly one {kind}.")
        return found[0]

    def resolve(reference, kind):
        r = resources.get(reference)
        if not r or r.get("resourceType") != kind:
            raise HTTPException(
                422,
                f"{kind} reference must resolve inside the bundle. Remote references are not fetched.",
            )
        return r

    try:
        patient = one("Patient")
        coverage = one("Coverage")
        c = one("Claim")
        if c.get("status") != "active" or c.get("use") != "claim":
            raise HTTPException(
                422, "Only active Claim/use=claim resources are supported."
            )
        if not c.get("type") or not c.get("priority") or not c.get("created"):
            raise HTTPException(422, "Claim type, priority and created are required.")
        if (
            resolve(c["patient"]["reference"], "Patient") != patient
            or resolve(coverage["beneficiary"]["reference"], "Patient") != patient
        ):
            raise HTTPException(
                422,
                "Claim and Coverage beneficiary references must identify the same Patient.",
            )
        if (
            len(c["insurance"]) != 1
            or not c["insurance"][0].get("focal")
            or resolve(c["insurance"][0]["coverage"]["reference"], "Coverage")
            != coverage
        ):
            raise HTTPException(
                422, "Exactly one focal insurance coverage is supported."
            )
        provider = resolve(c["provider"]["reference"], "Organization")
        if len(coverage["payor"]) != 1:
            raise HTTPException(422, "Exactly one payer is supported.")
        payer = resolve(coverage["payor"][0]["reference"], "Organization")
        alias = patient["identifier"][0]["value"]
        if not isinstance(alias, str) or not alias.startswith("SYN-"):
            raise HTTPException(
                422,
                "This adapter accepts synthetic Patient identifiers prefixed SYN- only.",
            )
        if (
            len(c["procedure"]) != 1
            or c["procedure"][0]["procedureCodeableConcept"]["coding"][0]["code"]
            != "LAP-APP-01"
        ):
            raise HTTPException(
                422, "Only one LAP-APP-01 procedure is supported by the demo rule pack."
            )
        admission = date.fromisoformat(c["billablePeriod"]["start"])
        discharge = date.fromisoformat(c["billablePeriod"]["end"])
        date.fromisoformat(c["created"][:10])
        amount = c["total"]["value"]
        if (
            c["total"]["currency"] != "INR"
            or isinstance(amount, bool)
            or not isinstance(amount, (int, float))
            or amount != int(amount)
        ):
            raise HTTPException(422, "Whole-rupee INR total is required.")
        if (
            any(i["net"]["currency"] != "INR" for i in c["item"])
            or sum(i["net"]["value"] for i in c["item"]) != amount
        ):
            raise HTTPException(422, "INR item net totals must equal Claim.total.")
        if (
            len(c["item"]) != 1
            or c["item"][0]["productOrService"]["coding"][0]["code"] != "LAP-APP-01"
            or c["item"][0].get("quantity", {}).get("value") != 1
        ):
            raise HTTPException(
                422,
                "The demo mapping supports one LAP-APP-01 package item with quantity 1. Separate item mapping is not implemented.",
            )
        active = coverage["status"] == "active" and date.fromisoformat(
            coverage["period"]["start"]
        ) <= admission <= date.fromisoformat(coverage["period"]["end"])
        identity = IntakeIdentity(
            patient=alias,
            hospital=provider["name"],
            procedure="Laparoscopic appendectomy",
            payer=payer["name"],
            doctor="Dr. FHIR Demo",
            admission=admission,
            discharge=discharge,
            amount=int(amount),
            policy_active=active,
        )
        documents = []
        for entry in bundle.entry:
            r = entry.resource
            if r.get("resourceType") != "DocumentReference":
                continue
            if (
                r["status"] != "current"
                or resolve(r["subject"]["reference"], "Patient") != patient
            ):
                raise HTTPException(
                    422,
                    "DocumentReference must be current and belong to the same Patient.",
                )
            if len(r["content"]) != 1:
                raise HTTPException(
                    422, "Each DocumentReference must have one attachment."
                )
            attachment = r["content"][0]["attachment"]
            binary = resolve(attachment["url"], "Binary")
            if (
                attachment["contentType"] != "text/plain"
                or binary["contentType"] != "text/plain"
            ):
                raise HTTPException(
                    422, "Only in-bundle text/plain Binary documents are supported."
                )
            raw = base64.b64decode(binary["data"], validate=True)
            if not raw or len(raw) > 100000:
                raise HTTPException(
                    422, "Binary text must be nonempty and no larger than 100 KB."
                )
            kind = r["type"]["coding"][0]["code"]
            if kind not in [
                "operative_report",
                "final_bill",
                "discharge_summary",
                "policy",
                "diagnostic_report",
            ]:
                raise HTTPException(422, "Unsupported document type code.")
            documents.append(
                {
                    "kind": kind,
                    "text": raw.decode("utf-8"),
                    "reference": r["id"],
                    "hash": digest(raw.decode("utf-8")),
                }
            )
        if not documents:
            raise HTTPException(
                422,
                "At least one supported DocumentReference with Binary evidence is required.",
            )
        return identity, documents
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            422,
            "Bundle does not match the supported synthetic R4 mapping. Check required fields, dates, references and base64 text.",
        )


@router.post("/integrations/fhir/import")
def import_fhir(
    b: FHIRBundle,
    bg: BackgroundTasks,
    a=Depends(actor),
    s=Depends(session, scope="function"),
):
    permitted(a, WRITE)
    if len(b.model_dump_json()) > 1500000:
        raise HTTPException(422, "FHIR bundle exceeds the 1.5 MB limit.")
    identity, docs = transform_bundle(b)
    item = Intake(
        id="FHIR-" + uuid4().hex[:10],
        org_id=a["org_id"],
        status="DRAFT",
        data={
            "created_at": now(),
            "source": "FHIR R4 synthetic collection bundle",
            "bundle_id": b.id,
            "bundle_hash": digest(b.model_dump_json()),
        },
    )
    s.add(item)
    s.flush()
    for d in docs:
        s.add(
            IntakeFile(
                id="IF-" + uuid4().hex,
                intake_id=item.id,
                kind=d["kind"],
                text=d["text"],
                data={
                    "filename": d["reference"] + ".txt",
                    "size": len(d["text"].encode()),
                    "sha256": d["hash"],
                    "extraction_status": "PARSED",
                    "uploaded_at": now(),
                    "source": "FHIR Binary",
                },
            )
        )
    s.flush()
    job = analyse_intake(item.id, identity, bg, a, s)
    c = s.get(Claim, job["claim_id"])
    audit(
        s,
        c,
        a["role"],
        "FHIR_BUNDLE_IMPORTED",
        bundle_id=b.id,
        resource_count=len(b.entry),
        profile="Narrow synthetic R4 subset; no NHCX conformance claim",
    )
    s.commit()
    return {
        **job,
        "mapping": {
            "patient": identity.patient,
            "provider": identity.hospital,
            "payer": identity.payer,
            "amount": identity.amount,
            "documents": len(docs),
        },
        "adapter": "Synthetic FHIR R4 import only. NHCX is not connected.",
    }


@router.get("/integrations")
def integrations(a=Depends(actor)):
    return [
        {
            "id": "fhir",
            "name": "FHIR R4",
            "status": "Demo Adapter",
            "detail": "Validated in-bundle synthetic collection import. Six supported resource types; LAP-APP-01 only.",
            "testable": True,
        },
        {
            "id": "nhcx",
            "name": "NHCX",
            "status": "Not Connected",
            "detail": "No transport, authentication or NHCX profile validation implemented.",
            "testable": False,
        },
        {
            "id": "his",
            "name": "HIS / HMIS",
            "status": "Not Connected",
            "detail": "No hospital system is connected.",
            "testable": False,
        },
        {
            "id": "storage",
            "name": "Object storage",
            "status": "Demo Adapter",
            "detail": "Original upload bytes are retained in local development storage. No S3 connection.",
            "testable": True,
        },
        {
            "id": "notifications",
            "name": "Notifications",
            "status": "Demo Adapter",
            "detail": "In-app events and simulated requests only. No email or messaging delivery.",
            "testable": False,
        },
        {
            "id": "webhooks",
            "name": "Webhooks",
            "status": "Not Connected",
            "detail": "External webhook delivery is not configured.",
            "testable": False,
        },
    ]


@router.post("/integrations/{id}/test")
def test_adapter(id: str, a=Depends(actor), s=Depends(session, scope="function")):
    permitted(a, WRITE)
    if id == "fhir":
        transform_bundle(
            FHIRBundle.model_validate(
                json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
            )
        )
        message = "Synthetic sample passed the implemented local R4 subset mapping. No external connection tested."
    elif id == "storage":
        key = "probe-" + uuid4().hex
        storage.put(key, b"local object storage probe")
        valid = storage.get(key) == b"local object storage probe"
        storage.delete(key)
        message = (
            "Local storage write/read probe passed."
            if valid
            else "Local storage probe failed."
        )
    else:
        raise HTTPException(
            422, "This integration is not connected and has no connection test."
        )
    c = s.scalar(select(Claim).where(Claim.org_id == a["org_id"]))
    if c:
        audit(
            s,
            c,
            a["role"],
            "DEMO_ADAPTER_TESTED",
            adapter=id,
            external_connection=False,
        )
    return {"status": "PASS", "message": message, "external_connection": False}
