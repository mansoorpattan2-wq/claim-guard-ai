from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4
from sqlalchemy import select
from .logging_config import event as log_event
from .db import (
    Claim,
    Document,
    Finding,
    Task,
    Audit,
    AgentRun,
    KnowledgeChunk,
    Organisation,
)

WEIGHTS = {
    "eligibility": 20,
    "documentation": 25,
    "policy": 20,
    "clinical": 15,
    "billing": 15,
    "integrity": 5,
}
AGENTS = [
    "Reading documents",
    "Validating eligibility",
    "Checking evidence",
    "Retrieving policy",
    "Checking clinical consistency",
    "Checking billing",
    "Checking integrity signals",
    "Preparing Claim Passport",
]
POLICY = [
    (
        "DOC-4.2",
        "Required surgical evidence",
        "For laparoscopic appendectomy (LAP-APP-01), a signed operative report identifying the beneficiary, procedure and service date is required. A discharge summary does not replace the operative report.",
        4,
        "4.2",
    ),
    (
        "PKG-6.1",
        "Package inclusions",
        "Package LAP-APP-01 includes surgeon fees, anaesthesia, theatre charges and standard consumables. Separately billed anaesthesia requires review against package inclusions.",
        6,
        "6.1",
    ),
    (
        "COV-2.1",
        "Coverage and validity",
        "Surgical inpatient treatment is supported when the policy is active on admission and the beneficiary identity matches. Conflicting identity or chronology requires human review.",
        2,
        "2.1",
    ),
    (
        "INT-8.1",
        "Integrity review",
        "Repeated document fingerprints across distinct beneficiaries and concentrated provider procedure activity are investigation leads. They do not establish fraud or determine claim denial.",
        8,
        "8.1",
    ),
]


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(text):
    return sha256(text.encode()).hexdigest()


def audit(s, c, actor, event, **data):
    log_event("audit_action", action=event, claim_id=c.id, actor_role=actor)
    s.add(
        Audit(
            id=str(uuid4()),
            claim_id=c.id,
            org_id=c.org_id,
            timestamp=now(),
            actor=actor,
            event=event,
            data={"trace_id": str(uuid4()), "version": "1.0", **data},
        )
    )


def evidence(s, key, service_date="2026-10-01"):
    k = s.get(KnowledgeChunk, key)
    if not k or not k.data["effective_date"] <= service_date <= k.data["expiry_date"]:
        return None
    return {"id": k.id, "text": k.text, **k.data}


def assess(c, docs, network=None):
    d = c.data
    operative = any(
        x.kind == "operative_report" and x.data.get("validated") for x in docs
    )
    checks = {
        "eligibility": 1.0,
        "documentation": 1.0 if operative else 0.24,
        "policy": 1.0,
        "clinical": 1.0 if operative else 0.2,
        "billing": 1.0,
        "integrity": 0.6,
    }
    issues = []
    if not operative:
        issues.append(
            (
                "F14",
                "Operative report missing",
                "evidence",
                "DOC-4.2",
                "BLOCKING",
                "A required surgical document is absent. Request the existing operative report from the hospital claims desk.",
            )
        )
    if not d["policy_active"]:
        checks["eligibility"] = 0
        issues.append(
            (
                "EL01",
                "Policy inactive on admission",
                "eligibility",
                "COV-2.1",
                "HIGH",
                "The recorded policy validity does not cover admission. A human must verify eligibility.",
            )
        )
    if d["discharge"] < d["admission"]:
        checks["eligibility"] = 0
        issues.append(
            (
                "F11",
                "Impossible chronology",
                "eligibility",
                "COV-2.1",
                "HIGH",
                "Discharge precedes admission. Verify the original dates.",
            )
        )
    if d.get("identity_conflict"):
        checks["clinical"] = 0
        issues.append(
            (
                "F12",
                "Identity inconsistency",
                "clinical",
                "COV-2.1",
                "HIGH",
                "Evidence contains a conflicting beneficiary identifier. Human review is required.",
            )
        )
    if any(x["category"] == "anaesthesia" for x in d["line_items"]):
        checks["billing"] = 0.2
        issues.append(
            (
                "F04",
                "Possible bundled charge",
                "billing",
                "PKG-6.1",
                "REVIEW",
                "₹12,000 anaesthesia is billed separately from the LAP-APP-01 package. Confirm whether it duplicates an included service.",
            )
        )
    if network and network.get("reused_claims"):
        checks["integrity"] = 0
        issues.append(
            (
                "F03",
                "Document reuse across beneficiaries",
                "network",
                "INT-8.1",
                "HIGH",
                f"The same diagnostic document fingerprint appears in {len(network['reused_claims'])} claims for distinct synthetic beneficiaries. Inspect the related sources.",
            )
        )
        if network["provider_ratio"] > 0.8 and network["provider_count"] >= 5:
            issues.append(
                (
                    "F08",
                    "Concentrated provider activity",
                    "network",
                    "INT-8.1",
                    "REVIEW",
                    f"{network['provider_matches']} of {network['provider_count']} claims at this provider use the documented procedure ({network['provider_ratio']:.0%}). This small synthetic sample is an investigation lead.",
                )
            )
    if operative:
        checks["billing"] = min(checks["billing"], d.get("billing_fraction", 1.0))
    score = round(sum(WEIGHTS[k] * v for k, v in checks.items()))
    state = "READY"
    if issues:
        state = "HUMAN_REVIEW"
    if not operative:
        state = "NEEDS_RESOLUTION"
        score = min(score, 63)
    if not d["policy_active"]:
        score = min(score, 49)
        state = "HUMAN_REVIEW"
    if d.get("identity_conflict"):
        score = min(score, 39)
        state = "HUMAN_REVIEW"
    if network and network.get("reused_claims"):
        state = "INVESTIGATION"
    return score, state, checks, issues


def analyse(s, c, targeted=False, record_runs=True, record_audit=True):
    docs = s.scalars(select(Document).where(Document.claim_id == c.id)).all()
    diagnostic_hashes = [d.hash for d in docs if d.kind == "diagnostic_report"]
    reused = (
        s.scalars(
            select(Claim)
            .join(Document)
            .where(Document.hash.in_(diagnostic_hashes), Claim.org_id == c.org_id)
        ).all()
        if diagnostic_hashes
        else []
    )
    distinct = {x.patient for x in reused}
    provider = s.scalars(
        select(Claim).where(Claim.hospital == c.hospital, Claim.org_id == c.org_id)
    ).all()
    matches = sum(x.procedure == c.procedure for x in provider)
    network = {
        "reused_claims": sorted({x.id for x in reused}) if len(distinct) > 1 else [],
        "provider_count": len(provider),
        "provider_matches": matches,
        "provider_ratio": matches / max(len(provider), 1),
    }
    score, state, checks, issues = assess(c, docs, network)
    overridden = {
        f.rule
        for f in s.scalars(select(Finding).where(Finding.claim_id == c.id))
        if f.data.get("review_disposition") == "OVERRIDE" and f.rule == "F04"
    }
    if "F04" in overridden:
        issues = [x for x in issues if x[0] != "F04"]
        checks["billing"] = 1.0
        score = round(sum(WEIGHTS[k] * v for k, v in checks.items()))
        if not issues:
            state = "READY"
    if evidence(s, "COV-2.1", c.data["admission"]) is None:
        issues.append(
            (
                "POL00",
                "Applicable policy source unavailable",
                "policy",
                "COV-2.1",
                "HIGH",
                "Policy check unavailable — human review required.",
            )
        )
        checks["policy"] = 0
        state = "HUMAN_REVIEW"
        score = min(score, 49)
    previous = {"readiness": c.readiness, "status": c.status}
    active = {x[0] for x in issues}
    for f in s.scalars(select(Finding).where(Finding.claim_id == c.id)):
        if f.rule not in active and f.rule not in overridden:
            f.status = "RESOLVED"
    for rule, title, agent, key, severity, description in issues:
        fid = f"{c.id}-{rule}"
        f = s.get(Finding, fid)
        citation = evidence(s, key, c.data["admission"])
        if citation is None:
            checks["policy"] = 0
            state = "HUMAN_REVIEW"
            score = min(score, 49)
            data = {
                "agent": agent,
                "severity": "HIGH",
                "description": "Policy check unavailable — human review required. No applicable source for this claim date.",
                "evidence": [],
                "confidence": {"extraction": 1.0, "evidence": 0, "interpretation": 0},
                "recommendation": "Request applicable policy source",
            }
        else:
            data = {
                "agent": agent,
                "severity": severity,
                "description": description,
                "evidence": [citation],
                "confidence": {
                    "extraction": 1.0,
                    "evidence": 1.0,
                    "interpretation": 0.95,
                },
                "recommendation": "Request operative report"
                if rule == "F14"
                else "Inspect evidence and request human review",
            }
        if not f:
            s.add(
                Finding(
                    id=fid,
                    claim_id=c.id,
                    rule=rule,
                    title=title,
                    status="OPEN",
                    data=data,
                )
            )
        else:
            f.status = "OPEN"
            f.data = data
        if rule == "F14" and not s.get(Task, f"RT-{c.id}"):
            s.add(
                Task(
                    id=f"RT-{c.id}",
                    claim_id=c.id,
                    finding_id=fid,
                    status="OPEN",
                    data={
                        "owner": "Hospital Claims Desk",
                        "required": "operative_report",
                        "created_at": now(),
                    },
                )
            )
    c.readiness = score
    c.status = state
    c.data = {
        **c.data,
        "checks": checks,
        "weights": WEIGHTS,
        "network_observed": network,
    }
    names = (
        [
            "Reading documents",
            "Checking evidence",
            "Checking clinical consistency",
            "Preparing Claim Passport",
        ]
        if targeted
        else AGENTS
    )
    for name in names:
        if record_runs:
            s.add(
                AgentRun(
                    id=str(uuid4()),
                    claim_id=c.id,
                    agent=name,
                    data={
                        "status": "COMPLETED",
                        "mode": "deterministic demo",
                        "version": "1.0",
                        "timestamp": now(),
                        "started_at": now(),
                        "ended_at": now(),
                        "duration_ms": 0,
                        "inputs_summary": f"{len(docs)} documents; claim {c.id}",
                        "tools": [
                            "SQLAlchemy",
                            "deterministic rules",
                            "effective-date source lookup",
                        ],
                        "next_transition": names[names.index(name) + 1]
                        if names.index(name) + 1 < len(names)
                        else state,
                        "targeted": targeted,
                        "input_hash": digest("|".join(sorted(x.hash for x in docs))),
                        "output": {"readiness": score, "state": state},
                        "evidence_refs": [x[3] for x in issues],
                        "finding_refs": [f"{c.id}-{x[0]}" for x in issues],
                    },
                )
            )
            if record_audit:
                audit(
                    s,
                    c,
                    name,
                    "AGENT_COMPLETED",
                    targeted=targeted,
                    evidence_refs=[x[3] for x in issues],
                )
    if record_audit:
        audit(
            s,
            c,
            "Readiness engine",
            "PASSPORT_UPDATED",
            previous=previous,
            new={"readiness": score, "status": state},
            checks=checks,
        )


def seed(s):
    if s.get(Claim, "CG001"):
        c = s.get(Claim, "CG021")
        if "billing_fraction" not in c.data:
            c.data = {**c.data, "billing_fraction": 11 / 15}
            analyse(s, c)
        for existing in s.scalars(select(Claim)).all():
            if "network_observed" not in existing.data:
                analyse(s, existing)
        s.commit()
        return
    s.add(Organisation(id="demo-hospital", name="Aster Grove Hospital Group"))
    s.flush()
    for key, title, text, page, section in POLICY:
        s.add(
            KnowledgeChunk(
                id=key,
                org_id="demo-hospital",
                text=text,
                data={
                    "title": title,
                    "source": "DemoCare Health Insurance Policy 2026",
                    "authority": "Synthetic insurer • demonstration only",
                    "version": "1.0",
                    "effective_date": "2026-01-01",
                    "expiry_date": "2026-12-31",
                    "page": page,
                    "section": section,
                    "document_type": "synthetic_policy",
                    "agent": "Policy retrieval",
                    "timestamp": now(),
                },
            )
        )
    s.flush()
    for i in range(1, 51):
        cid = f"CG{i:03}"
        category = (
            "clean"
            if i <= 20
            else "missing_evidence"
            if i <= 28
            else "billing"
            if i <= 35
            else "eligibility"
            if i <= 40
            else "identity"
            if i <= 44
            else "network"
        )
        data = {
            "payer": "DemoCare Health",
            "owner": "Meera Shah",
            "admission": "2026-10-01",
            "discharge": "2026-10-03",
            "policy_active": category != "eligibility",
            "policy_id": f"DC-2026-{i:03}",
            "doctor": "Dr. A. Sen" if i >= 45 else "Dr. Kavya Rao",
            "package": "LAP-APP-01",
            "cluster": i >= 45,
            "identity_conflict": category == "identity",
            "line_items": [
                {
                    "description": "Laparoscopic appendectomy package",
                    "category": "package",
                    "amount": 78000,
                }
            ],
            "ground_truth": {
                "category": category,
                "expected_state": {
                    "clean": "READY",
                    "missing_evidence": "NEEDS_RESOLUTION",
                    "billing": "HUMAN_REVIEW",
                    "eligibility": "HUMAN_REVIEW",
                    "identity": "HUMAN_REVIEW",
                    "network": "INVESTIGATION",
                }[category],
                "injected_defects": [] if category == "clean" else [category],
            },
        }
        if category == "billing":
            data["line_items"].append(
                {
                    "description": "Anaesthesia",
                    "category": "anaesthesia",
                    "amount": 12000,
                }
            )
        if cid == "CG021":
            data["billing_fraction"] = 11 / 15
        c = Claim(
            id=cid,
            org_id="demo-hospital",
            patient=f"Beneficiary {i:03}",
            hospital="Meridian Surgical Centre"
            if i >= 45
            else [
                "Aster Grove Hospital",
                "Oakbridge Medical Centre",
                "Riverstone Hospital",
            ][i % 3],
            procedure="Laparoscopic appendectomy"
            if i >= 21 or i % 2
            else "Day-care cataract surgery",
            amount=sum(x["amount"] for x in data["line_items"]),
            status="READY",
            readiness=0,
            data=data,
        )
        s.add(c)
        s.flush()
        kinds = ["discharge_summary", "final_bill", "policy", "diagnostic_report"] + (
            [] if category == "missing_evidence" else ["operative_report"]
        )
        for kind in kinds:
            text = f"SYNTHETIC DOCUMENT — DEMONSTRATION ONLY\nClaim: {cid}\nBeneficiary: {c.patient}\nProcedure: {c.procedure}\nService date: 2026-10-02\nDocument type: {kind}\nRecorded and signed by {data['doctor']}.\nNo real patient information."
            if category == "network" and kind == "diagnostic_report":
                text = "SYNTHETIC SHARED DIAGNOSTIC REPORT — identical seeded fingerprint for investigation testing."
            s.add(
                Document(
                    id=f"{cid}-{kind}",
                    claim_id=cid,
                    kind=kind,
                    title=kind.replace("_", " ").title(),
                    text=text,
                    hash=digest(text),
                    data={
                        "validated": True,
                        "page": 1,
                        "version": "1.0",
                        "timestamp": now(),
                    },
                )
            )
        s.flush()
    for c in s.scalars(select(Claim)).all():
        analyse(s, c)
    s.commit()
