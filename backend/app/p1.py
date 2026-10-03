"""Additive P1 workflows. Existing P0 endpoint semantics stay unchanged."""

import io
import os
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from .db import (
    Session,
    Claim,
    Document,
    Finding,
    Task,
    HumanDecision,
    AgentRun,
    KnowledgeChunk,
    KnowledgeSource,
    Intake,
    IntakeFile,
    AnalysisJob,
    Audit,
    Migration,
)
from .engine import AGENTS, POLICY, WEIGHTS, analyse, audit, evidence, now, digest
from .main import actor, session, permitted, claim, row, passport, WRITE, REVIEW
from .main import require_reset_key
from .storage import storage
from .logging_config import event

router = APIRouter(prefix="/api")
KINDS = [
    "operative_report",
    "discharge_summary",
    "final_bill",
    "policy",
    "diagnostic_report",
    "pre_authorisation",
    "unknown",
]
TOOLS = {
    "Reading documents": ["structured field parser", "SHA-256"],
    "Validating eligibility": ["date comparison", "policy validity"],
    "Checking evidence": ["document inventory", "source requirements"],
    "Retrieving policy": [
        "keyword retrieval",
        "effective-date and organisation filter",
    ],
    "Checking clinical consistency": ["documented identity comparison"],
    "Checking billing": ["arithmetic", "package inclusion rule"],
    "Checking integrity signals": [
        "org-scoped fingerprint lookup",
        "provider aggregates",
    ],
    "Preparing Claim Passport": ["readiness engine", "hard gates", "audit writer"],
}


def bootstrap(s):
    if not s.get(KnowledgeSource, "DC-2026"):
        s.add(
            KnowledgeSource(
                id="DC-2026",
                org_id="demo-hospital",
                title="DemoCare Health Insurance Policy 2026",
                status="ACTIVE",
                data={
                    "authority": "Synthetic insurer — demonstration only",
                    "version": "1.0",
                    "effective_date": "2026-01-01",
                    "expiry_date": "2026-12-31",
                    "chunk_ids": [p[0] for p in POLICY],
                    "retrieval": "Deterministic keyword + rule lookup (no vector service)",
                },
            )
        )
        s.add(
            KnowledgeSource(
                id="DC-2025",
                org_id="demo-hospital",
                title="DemoCare Policy 2025 (superseded)",
                status="SUPERSEDED",
                data={
                    "authority": "Synthetic insurer — demonstration only",
                    "version": "0.9",
                    "effective_date": "2025-01-01",
                    "expiry_date": "2025-12-31",
                    "chunk_ids": [],
                    "retrieval": "Not indexed / superseded",
                },
            )
        )
    recover_jobs(s)


def recover_jobs(s):
    # A process restart cannot safely resume a partially executing job silently.
    for job in s.scalars(
        select(AnalysisJob).where(AnalysisJob.status.in_(["QUEUED", "RUNNING"]))
    ):
        job.status = "FAILED"
        job.data = {
            **job.data,
            "error": "Execution interrupted by service restart. Retry analysis.",
            "ended_at": now(),
        }
        c = s.get(Claim, job.claim_id)
        c.status = "HUMAN_REVIEW"
        c.readiness = min(c.readiness, 49)
        for run in s.scalars(select(AgentRun).where(AgentRun.claim_id == c.id)):
            if run.data.get("job_id") == job.id and run.data.get("status") == "RUNNING":
                run.data = {
                    **run.data,
                    "status": "FAILED",
                    "ended_at": now(),
                    "error": job.data["error"],
                    "next_transition": "HUMAN_REVIEW",
                }
        set_intake_status(s, c, "FAILED", job.id)
        audit(
            s,
            c,
            "system",
            "ANALYSIS_INTERRUPTED",
            job_id=job.id,
            error=job.data["error"],
        )
    s.commit()


def set_intake_status(s, c, status, job_id):
    item = s.scalar(select(Intake).where(Intake.claim_id == c.id))
    if item:
        item.status = status
        item.data = {**item.data, "job_id": job_id}


def classify(name, text):
    content = (name + " " + text[:1200]).lower().replace("_", " ")
    for kind, terms in [
        (
            "operative_report",
            ["operative report", "operative note", "operating report"],
        ),
        ("discharge_summary", ["discharge summary"]),
        ("final_bill", ["invoice", "final bill", "anaesthesia charge"]),
        (
            "diagnostic_report",
            ["diagnostic report", "laboratory report", "ultrasound report"],
        ),
        ("pre_authorisation", ["pre-auth", "preauthorisation"]),
        ("policy", ["insurance policy", "policy wording"]),
    ]:
        if any(term in content for term in terms):
            return kind
    return "unknown"


def fields(text):
    result = {}
    for key in [
        "Beneficiary",
        "Hospital",
        "Procedure",
        "Admission",
        "Discharge",
        "Service date",
        "Payer",
        "Doctor",
        "Amount",
        "Policy active",
    ]:
        vals = re.findall(r"^" + re.escape(key) + r":[ \t]*([^\r\n]+)", text, re.M)
        if len(set(vals)) == 1:
            result[key] = vals[0].strip()
        elif len(set(vals)) > 1:
            result[key] = "CONFLICT"
    return result


def parse_file(name, raw):
    suffix = Path(name).suffix.lower()
    if suffix == ".txt":
        try:
            return raw.decode("utf-8-sig"), "PARSED"
        except UnicodeDecodeError:
            raise HTTPException(422, "Text files must use UTF-8.")
    if suffix == ".pdf":
        if not raw.startswith(b"%PDF"):
            raise HTTPException(422, "PDF signature is invalid.")
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(raw))
            if len(reader.pages) > 30:
                raise HTTPException(422, "Maximum 30 PDF pages per document.")
            text = "\n".join(p.extract_text() or "" for p in reader.pages)
            return text[:100000], "PARSED" if text.strip() else "UNREADABLE"
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                422, "PDF could not be parsed. Upload a readable text or PDF source."
            )
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                if sum(f.file_size for f in z.infolist()) > 4000000:
                    raise HTTPException(422, "Expanded DOCX exceeds 4 MB.")
                root = ET.fromstring(z.read("word/document.xml"))
                paragraphs = root.findall(
                    ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
                )
                text = "\n".join("".join(p.itertext()) for p in paragraphs)
                return text[:100000], "PARSED" if text.strip() else "UNREADABLE"
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "DOCX could not be parsed.")
    if suffix in [".png", ".jpg", ".jpeg"]:
        valid = (
            raw.startswith(b"\x89PNG\r\n\x1a\n")
            if suffix == ".png"
            else raw.startswith(b"\xff\xd8\xff")
        )
        if not valid:
            raise HTTPException(422, "Image signature is invalid.")
        return "", "UNREADABLE"
    raise HTTPException(
        422,
        "Supported files: UTF-8 TXT, text PDF, DOCX, PNG and JPEG. Images require clearer text evidence; OCR is not connected.",
    )


def get_intake(s, id, a):
    item = s.get(Intake, id)
    if not item or item.org_id != a["org_id"]:
        raise HTTPException(404, "Intake not found.")
    return item


def intake_view(s, item):
    files = s.scalars(select(IntakeFile).where(IntakeFile.intake_id == item.id)).all()
    previews = [fields(f.text) for f in files]
    identity = {}
    conflicts = []
    for key in [
        "Beneficiary",
        "Hospital",
        "Procedure",
        "Admission",
        "Discharge",
        "Payer",
        "Doctor",
        "Amount",
        "Policy active",
    ]:
        vals = {p[key] for p in previews if p.get(key)}
        if len(vals) > 1 or "CONFLICT" in vals:
            conflicts.append(key)
        elif vals:
            identity[key] = next(iter(vals))
    return {
        **row(item),
        "files": [{"id": f.id, "kind": f.kind, "data": f.data} for f in files],
        "identity": identity,
        "conflicts": conflicts,
    }


@router.post("/intakes")
def create_intake(a=Depends(actor), s=Depends(session, scope="function")):
    permitted(a, WRITE)
    item = Intake(
        id="IN-" + uuid4().hex[:10],
        org_id=a["org_id"],
        status="DRAFT",
        data={"created_at": now(), "created_by": a["id"]},
    )
    s.add(item)
    s.flush()
    return intake_view(s, item)


@router.get("/intakes/{id}")
def get_preview(id: str, a=Depends(actor), s=Depends(session, scope="function")):
    return intake_view(s, get_intake(s, id, a))


@router.post("/intakes/{id}/files")
def upload(
    id: str,
    files: list[UploadFile] = File(...),
    a=Depends(actor),
    s=Depends(session, scope="function"),
):
    permitted(a, WRITE)
    item = get_intake(s, id, a)
    if item.status != "DRAFT":
        raise HTTPException(409, "This intake has already been analysed.")
    existing = s.scalars(select(IntakeFile).where(IntakeFile.intake_id == id)).all()
    if not 1 <= len(files) or len(files) + len(existing) > 20:
        raise HTTPException(422, "Upload between 1 and 20 documents per intake.")
    additions = []
    for f in files:
        raw = f.file.read(2000001)
        if not raw or len(raw) > 2000000:
            raise HTTPException(422, "Each file must be nonempty and at most 2 MB.")
        name = Path((f.filename or "document.txt").replace("\\", "/")).name
        text, status = parse_file(name, raw)
        kind = classify(name, text) if text else "unknown"
        fid = "IF-" + uuid4().hex
        # Original upload is kept under an opaque name, never under a client path.
        additions.append((fid, name, raw, text, status, kind))
    for fid, name, raw, text, status, kind in additions:
        storage.put(fid, raw)
        s.add(
            IntakeFile(
                id=fid,
                intake_id=id,
                kind=kind,
                text=text,
                data={
                    "filename": name,
                    "size": len(raw),
                    "sha256": __import__("hashlib").sha256(raw).hexdigest(),
                    "extraction_status": status,
                    "confidence": 1.0 if status == "PARSED" else 0,
                    "uploaded_at": now(),
                    "storage_key": fid,
                },
            )
        )
    s.flush()
    return intake_view(s, item)


class Classification(BaseModel):
    kind: str


@router.post("/intakes/{id}/files/{file_id}/classification")
def correct_classification(
    id: str,
    file_id: str,
    b: Classification,
    a=Depends(actor),
    s=Depends(session, scope="function"),
):
    permitted(a, WRITE)
    item = get_intake(s, id, a)
    f = s.get(IntakeFile, file_id)
    if item.status != "DRAFT":
        raise HTTPException(409, "Classification is frozen after intake analysis.")
    if not f or f.intake_id != id:
        raise HTTPException(404, "Document not found.")
    if b.kind not in KINDS:
        raise HTTPException(422, "Unknown document classification.")
    f.data = {
        **f.data,
        "original_classification": f.data.get("original_classification", f.kind),
        "corrected_by": a["id"],
    }
    f.kind = b.kind
    s.flush()
    return intake_view(s, item)


class IntakeIdentity(BaseModel):
    patient: str = Field(min_length=3, max_length=100)
    hospital: str = Field(min_length=3, max_length=150)
    procedure: str = Field(min_length=3, max_length=150)
    payer: str = Field(default="DemoCare Health", max_length=100)
    doctor: str = Field(default="Unspecified provider", max_length=100)
    admission: date
    discharge: date
    amount: int = Field(gt=0, le=10000000)
    policy_active: bool


def job_view(job):
    return row(job)


def run_job(job_id):
    event("analysis_started", job_id=job_id)
    for index, name in enumerate(AGENTS):
        started = now()
        clock = time.perf_counter()
        run_id = str(uuid4())
        try:
            with Session() as s:
                job = s.get(AnalysisJob, job_id)
                c = s.get(Claim, job.claim_id)
                job.status = "RUNNING"
                job.data = {
                    **job.data,
                    "current_step": index,
                    "started_at": job.data.get("started_at", started),
                }
                s.add(
                    AgentRun(
                        id=run_id,
                        claim_id=c.id,
                        agent=name,
                        data={
                            "status": "RUNNING",
                            "started_at": started,
                            "job_id": job_id,
                            "version": "1.1",
                            "mode": "deterministic",
                            "tools": TOOLS[name],
                        },
                    )
                )
                s.commit()
            with Session() as s:
                job = s.get(AnalysisJob, job_id)
                c = s.get(Claim, job.claim_id)
                docs = s.scalars(
                    select(Document).where(Document.claim_id == c.id)
                ).all()
                refs = []
                result = {}
                findings = []
                if index == 0:
                    result = {
                        "document_count": len(docs),
                        "unreadable": sum(not d.data.get("validated") for d in docs),
                    }
                elif index == 1:
                    result = {
                        "policy_active": c.data["policy_active"],
                        "chronology_valid": c.data["discharge"] >= c.data["admission"],
                    }
                elif index == 2:
                    required = evidence(s, "DOC-4.2", c.data["admission"])
                    refs = ["DOC-4.2"] if required else []
                    result = {
                        "operative_report": "PRESENT"
                        if any(
                            d.kind == "operative_report" and d.data.get("validated")
                            for d in docs
                        )
                        else "MISSING",
                        "requirement_supported": bool(required),
                    }
                elif index == 3:
                    chunks = retrieve(
                        s,
                        a={"org_id": c.org_id},
                        query="coverage required documents package anaesthesia",
                        service_date=c.data["admission"],
                    )
                    refs = [x["id"] for x in chunks]
                    result = {
                        "retrieved": len(chunks),
                        "applicable_date": c.data["admission"],
                    }
                    if not chunks:
                        raise ValueError(
                            "Policy check unavailable — human review required. No applicable active source."
                        )
                elif index == 4:
                    result = {
                        "identity_conflict": c.data.get("identity_conflict", False),
                        "mode": "Comparison of documented fields; no diagnosis",
                    }
                elif index == 5:
                    result = {
                        "line_total": sum(x["amount"] for x in c.data["line_items"]),
                        "claim_amount": c.amount,
                        "package_separate_anaesthesia": any(
                            x["category"] == "anaesthesia" for x in c.data["line_items"]
                        ),
                    }
                    refs = ["PKG-6.1"]
                elif index == 6:
                    hashes = [d.hash for d in docs]
                    result = {
                        "shared_hash_claims": sorted(
                            set(
                                s.scalars(
                                    select(Document.claim_id)
                                    .join(Claim, Document.claim_id == Claim.id)
                                    .where(
                                        Document.hash.in_(hashes),
                                        Claim.org_id == c.org_id,
                                        Claim.id != c.id,
                                    )
                                ).all()
                            )
                        )
                    }
                else:
                    analyse(s, c, record_runs=False)
                    if c.data.get("extraction_unavailable"):
                        c.status = "HUMAN_REVIEW"
                        c.readiness = min(c.readiness, 49)
                        c.data = {**c.data, "extraction_state": "INSUFFICIENT_EVIDENCE"}
                        fid = c.id + "-EX01"
                        if not s.get(Finding, fid):
                            s.add(
                                Finding(
                                    id=fid,
                                    claim_id=c.id,
                                    rule="EX01",
                                    title="Low-confidence document extraction",
                                    status="OPEN",
                                    data={
                                        "agent": "intake",
                                        "severity": "HIGH",
                                        "description": "An unreadable or unclassified source requires clearer evidence or human extraction. The check is not passed.",
                                        "evidence": [],
                                        "confidence": {
                                            "extraction": 0,
                                            "evidence": 0,
                                            "interpretation": 0,
                                        },
                                        "recommendation": "Request a readable text source or specialist review.",
                                    },
                                )
                            )
                    findings = [
                        f.id
                        for f in s.scalars(
                            select(Finding).where(
                                Finding.claim_id == c.id, Finding.status == "OPEN"
                            )
                        )
                    ]
                    result = {"readiness": c.readiness, "state": c.status}
                ended = now()
                run = s.get(AgentRun, run_id)
                run.data = {
                    **run.data,
                    "status": "COMPLETED",
                    "ended_at": ended,
                    "duration_ms": round((time.perf_counter() - clock) * 1000, 2),
                    "inputs_summary": f"{len(docs)} source documents; {c.patient}; {c.procedure}",
                    "input_hash": digest("|".join(sorted(d.hash for d in docs))),
                    "output": result,
                    "evidence_refs": refs,
                    "finding_refs": findings,
                    "next_transition": AGENTS[index + 1] if index < 7 else c.status,
                    "rationale": "Computed from persisted claim fields, documents and applicable synthetic policy.",
                }
                steps = [*job.data.get("steps", []), {"agent": name, **run.data}]
                job.data = {**job.data, "steps": steps}
                audit(
                    s,
                    c,
                    name,
                    "AGENT_COMPLETED",
                    job_id=job_id,
                    evidence_refs=refs,
                    result=result,
                )
                if index == 7:
                    job.status = "COMPLETED"
                    job.data = {**job.data, "ended_at": ended}
                    set_intake_status(s, c, "COMPLETED", job.id)
                s.commit()
        except Exception as exc:
            with Session() as s:
                job = s.get(AnalysisJob, job_id)
                c = s.get(Claim, job.claim_id)
                run = s.get(AgentRun, run_id)
                message = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else "Agent execution failed. Retry or request human review."
                )
                analyse(s, c, record_runs=False)
                if run:
                    run.data = {
                        **run.data,
                        "status": "FAILED",
                        "ended_at": now(),
                        "duration_ms": round((time.perf_counter() - clock) * 1000, 2),
                        "error": message,
                        "next_transition": "HUMAN_REVIEW",
                    }
                job.status = "FAILED"
                job.data = {
                    **job.data,
                    "error": message,
                    "failed_step": name,
                    "ended_at": now(),
                }
                c.status = "HUMAN_REVIEW"
                c.readiness = min(c.readiness, 49)
                set_intake_status(s, c, "FAILED", job.id)
                audit(s, c, name, "AGENT_FAILED", job_id=job_id, error=message)
                s.commit()
            return


def enqueue(s, c):
    job = AnalysisJob(
        id="JOB-" + uuid4().hex[:12],
        claim_id=c.id,
        status="QUEUED",
        data={"created_at": now(), "steps": [], "current_step": 0},
    )
    s.add(job)
    set_intake_status(s, c, "ANALYSING", job.id)
    s.commit()
    return job


@router.post("/intakes/{id}/analyse")
def analyse_intake(
    id: str,
    b: IntakeIdentity,
    bg: BackgroundTasks,
    a=Depends(actor),
    s=Depends(session, scope="function"),
):
    from .main import LOCK

    with LOCK:
        return _analyse_intake(id, b, bg, a, s)


def _analyse_intake(id, b, bg, a, s):
    permitted(a, WRITE)
    item = get_intake(s, id, a)
    if item.status == "ARCHIVED":
        raise HTTPException(
            409, "This intake belongs to a prior presentation. Start a new intake."
        )
    if item.claim_id:
        return job_view(
            s.scalar(
                select(AnalysisJob)
                .where(AnalysisJob.claim_id == item.claim_id)
                .order_by(AnalysisJob.data["created_at"].as_string().desc())
            )
        )
    files = s.scalars(select(IntakeFile).where(IntakeFile.intake_id == id)).all()
    if not files:
        raise HTTPException(422, "Upload at least one source document before analysis.")
    if b.procedure != "Laparoscopic appendectomy":
        raise HTTPException(
            422,
            "Current intake rule pack supports Laparoscopic appendectomy / LAP-APP-01 only. Other procedures require a new governed rule pack.",
        )
    if b.discharge < b.admission:
        raise HTTPException(422, "Discharge cannot precede admission.")
    preview = intake_view(s, item)
    conflict = bool(preview["conflicts"])
    for f in files:
        extracted = fields(f.text)
        if extracted.get("Beneficiary") and extracted["Beneficiary"] != b.patient:
            conflict = True
        if extracted.get("Procedure") and extracted["Procedure"] != b.procedure:
            conflict = True
    cid = "CLM-" + uuid4().hex[:8].upper()
    data = {
        **b.model_dump(mode="json"),
        "payer": b.payer,
        "owner": a["role"],
        "doctor": b.doctor,
        "policy_id": "CONFIRMED-DEMO-POLICY",
        "package": "LAP-APP-01",
        "identity_conflict": conflict,
        "line_items": [
            {
                "description": "LAP-APP-01 package",
                "category": "package",
                "amount": b.amount,
            }
        ],
        "ground_truth": {"category": "uploaded"},
        "intake_id": id,
        "extraction_unavailable": any(
            f.data["extraction_status"] != "PARSED" or f.kind == "unknown"
            for f in files
        ),
        "checks": {},
        "weights": WEIGHTS,
    }
    c = Claim(
        id=cid,
        org_id=a["org_id"],
        patient=b.patient,
        hospital=b.hospital,
        procedure=b.procedure,
        amount=b.amount,
        status="HUMAN_REVIEW",
        readiness=0,
        data=data,
    )
    s.add(c)
    s.flush()
    for f in files:
        parsed = fields(f.text)
        validated = f.data["extraction_status"] == "PARSED" and bool(f.text.strip())
        if f.kind == "operative_report":
            try:
                service_date = date.fromisoformat(parsed.get("Service date", ""))
                service_valid = b.admission <= service_date <= b.discharge
            except ValueError:
                service_valid = False
            validated = (
                validated
                and parsed.get("Beneficiary") == b.patient
                and parsed.get("Procedure") == b.procedure
                and bool(re.search(r"^Signed by:[ \t]*\S+", f.text, re.M))
                and service_valid
            )
        s.add(
            Document(
                id="DOC-" + uuid4().hex,
                claim_id=cid,
                kind=f.kind,
                title=f.data["filename"],
                text=f.text
                or "UNREADABLE SOURCE — clearer evidence or manual extraction required.",
                hash=f.data["sha256"],
                data={
                    **f.data,
                    "validated": bool(validated),
                    "page": 1,
                    "version": "1.0",
                    "timestamp": now(),
                    "source": "user upload",
                },
            )
        )
    item.claim_id = cid
    item.status = "ANALYSING"
    audit(
        s,
        c,
        a["role"],
        "CLAIM_INTAKE_CREATED",
        intake_id=id,
        documents=len(files),
        identity_conflict=conflict,
    )
    job = enqueue(s, c)
    bg.add_task(run_job, job.id)
    return job_view(job)


@router.get("/analysis-jobs/{id}")
def job_status(id: str, a=Depends(actor), s=Depends(session, scope="function")):
    job = s.get(AnalysisJob, id)
    if not job:
        raise HTTPException(404, "Analysis job not found.")
    claim(s, job.claim_id, a)
    return job_view(job)


@router.post("/analysis-jobs/{id}/retry")
def retry(
    id: str, bg: BackgroundTasks, a=Depends(actor), s=Depends(session, scope="function")
):
    permitted(a, WRITE)
    job = s.get(AnalysisJob, id)
    if not job:
        raise HTTPException(404, "Analysis job not found.")
    c = claim(s, job.claim_id, a)
    if job.status != "FAILED":
        raise HTTPException(409, "Only failed jobs may be retried.")
    fresh = enqueue(s, c)
    audit(s, c, a["role"], "ANALYSIS_RETRIED", previous_job=id, new_job=fresh.id)
    s.commit()
    bg.add_task(run_job, fresh.id)
    return job_view(fresh)


@router.get("/review")
def review_queue(a=Depends(actor), s=Depends(session, scope="function")):
    return [
        {"claim": row(c), "finding": row(f)}
        for f, c in s.execute(
            select(Finding, Claim)
            .join(Claim)
            .where(
                Claim.org_id == a["org_id"],
                Claim.data["demo_archived"].as_boolean().is_not(True),
                Finding.status.in_(
                    ["OPEN", "CONFIRMED", "INFORMATION_REQUESTED", "ESCALATED"]
                ),
                Finding.rule != "F14",
                Claim.status == "HUMAN_REVIEW",
            )
        )
    ]


class ReviewDecision(BaseModel):
    decision: str
    reason: str = Field(default="", max_length=2000)


@router.post("/review/{id}/decision")
def review_decision(
    id: str, b: ReviewDecision, a=Depends(actor), s=Depends(session, scope="function")
):
    permitted(a, REVIEW)
    f = s.get(Finding, id)
    if not f:
        raise HTTPException(404, "Finding not found.")
    c = claim(s, f.claim_id, a)
    if b.decision not in ["AGREE", "OVERRIDE", "REQUEST_INFORMATION", "ESCALATE"]:
        raise HTTPException(422, "Unknown human disposition.")
    if b.decision == "OVERRIDE" and len(b.reason.strip()) < 3:
        raise HTTPException(
            422, "Override requires an explanation of at least three characters."
        )
    if f.rule == "F14" and b.decision == "OVERRIDE":
        raise HTTPException(
            422,
            "A required missing document cannot be overridden through policy review. Resolve the evidence task.",
        )
    old_state = c.status
    statuses = {
        "AGREE": "CONFIRMED",
        "OVERRIDE": "OVERRIDDEN",
        "REQUEST_INFORMATION": "INFORMATION_REQUESTED",
        "ESCALATE": "ESCALATED",
    }
    f.status = statuses[b.decision]
    f.data = {
        **f.data,
        "review_disposition": b.decision,
        "review_reason": b.reason.strip(),
        "reviewer": a["role"],
        "reviewed_at": now(),
    }
    s.add(
        HumanDecision(
            id=str(uuid4()),
            finding_id=id,
            data={
                "decision": b.decision,
                "reason": b.reason.strip(),
                "reviewer": a["role"],
                "timestamp": now(),
                "original_finding": {
                    "title": f.title,
                    "rule": f.rule,
                    "description": f.data["description"],
                    "evidence": f.data["evidence"],
                },
            },
        )
    )
    s.flush()
    if b.decision == "OVERRIDE" and f.rule == "F04":
        remaining = s.scalars(
            select(Finding).where(
                Finding.claim_id == c.id,
                Finding.status.in_(
                    ["OPEN", "CONFIRMED", "INFORMATION_REQUESTED", "ESCALATED"]
                ),
            )
        ).all()
        checks = {**c.data["checks"], "billing": 1.0}
        c.data = {**c.data, "checks": checks}
        c.readiness = round(sum(WEIGHTS[k] * v for k, v in checks.items()))
        if (
            not remaining
            and c.data["policy_active"]
            and not c.data.get("identity_conflict")
        ):
            c.status = "READY"
    if b.decision in ["REQUEST_INFORMATION", "ESCALATE"]:
        c.status = "HUMAN_REVIEW"
    audit(
        s,
        c,
        a["role"],
        "REVIEW_" + b.decision,
        finding_id=id,
        reason=b.reason.strip(),
        previous_state=old_state,
        new_state=c.status,
        readiness=c.readiness,
        external_delivery=False,
    )
    return passport(s, c)


def retrieve(s, a, query, service_date):
    try:
        date.fromisoformat(service_date)
    except ValueError:
        raise HTTPException(422, "Applicable date must use YYYY-MM-DD.")
    words = set(re.findall(r"[a-z0-9]+", query.lower()))
    source = s.scalar(
        select(KnowledgeSource).where(
            KnowledgeSource.org_id == a["org_id"], KnowledgeSource.status == "ACTIVE"
        )
    )
    if (
        not source
        or not source.data["effective_date"]
        <= service_date
        <= source.data["expiry_date"]
    ):
        return []
    candidates = []
    for chunk in s.scalars(
        select(KnowledgeChunk).where(
            KnowledgeChunk.org_id == a["org_id"],
            KnowledgeChunk.id.in_(source.data["chunk_ids"]),
        )
    ):
        if (
            not chunk.data["effective_date"]
            <= service_date
            <= chunk.data["expiry_date"]
        ):
            continue
        overlap = words.intersection(
            set(
                re.findall(
                    r"[a-z0-9]+", (chunk.text + " " + chunk.data["title"]).lower()
                )
            )
        )
        if overlap:
            candidates.append(
                {
                    "id": chunk.id,
                    "text": chunk.text,
                    **chunk.data,
                    "score": round(len(overlap) / max(len(words), 1), 4),
                    "matched_terms": sorted(overlap),
                }
            )
    candidates.sort(key=lambda c: (-c["score"], c["id"]))
    return [{**c, "rank": i + 1} for i, c in enumerate(candidates[:4])]


@router.get("/knowledge/catalog")
def catalog(a=Depends(actor), s=Depends(session, scope="function")):
    return [
        {**row(x), "chunk_count": len(x.data["chunk_ids"])}
        for x in s.scalars(
            select(KnowledgeSource).where(KnowledgeSource.org_id == a["org_id"])
        )
    ]


class QueryBody(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    applicable_date: date


@router.post("/knowledge/retrieve")
def retrieval_test(
    b: QueryBody, a=Depends(actor), s=Depends(session, scope="function")
):
    passages = retrieve(s, a, b.query, b.applicable_date.isoformat())
    billing = next((p for p in passages if p["id"] == "PKG-6.1"), None)
    if not passages:
        answer = "INSUFFICIENT_EVIDENCE — no active, applicable source supports this query. Human review required."
    elif billing and any(
        x in b.query.lower() for x in ["anaesthesia", "anesthesia", "lap-app-01"]
    ):
        answer = "The synthetic LAP-APP-01 package includes anaesthesia. Separate anaesthesia billing requires human review against package inclusions. This is a demo policy interpretation, not an insurer adjudication."
    else:
        answer = "Retrieved source excerpts are shown below. A broader conclusion is not supported by this deterministic retrieval adapter; human interpretation is required."
    c = s.scalar(select(Claim).where(Claim.org_id == a["org_id"]))
    if c:
        audit(
            s,
            c,
            a["role"],
            "RETRIEVAL_TESTED",
            query=b.query,
            applicable_date=b.applicable_date.isoformat(),
            evidence_refs=[p["id"] for p in passages],
        )
    return {
        "answer": answer,
        "status": "GROUNDED" if billing else "HUMAN_REVIEW",
        "passages": passages,
        "citations": [billing["id"]] if billing else [],
        "applicable_date": b.applicable_date.isoformat(),
        "method": "Deterministic keyword ranking; no vector or LLM service",
    }


@router.get("/claims/{id}/printable")
def printable(id: str, a=Depends(actor), s=Depends(session, scope="function")):
    from .printable import render

    c = claim(s, id, a)
    audit(s, c, a["role"], "PRINTABLE_PASSPORT_GENERATED", generated_at=now())
    return HTMLResponse(render(passport(s, c)))


def reset_demo(s, a):
    if os.getenv("DEMO_MODE", "true") != "true":
        raise HTTPException(403, "Demo reset is disabled.")
    active = s.scalar(
        select(AnalysisJob)
        .join(Claim)
        .where(
            Claim.org_id == a["org_id"], AnalysisJob.status.in_(["QUEUED", "RUNNING"])
        )
    )
    if active:
        raise HTTPException(
            409,
            "Wait for running analysis to finish before resetting the presentation.",
        )
    claims = s.scalars(select(Claim).where(Claim.org_id == a["org_id"])).all()
    ids = [c.id for c in claims]
    for model, query in [
        (Audit, select(Audit).where(Audit.org_id == a["org_id"])),
        (AgentRun, select(AgentRun).where(AgentRun.claim_id.in_(ids))),
        (
            HumanDecision,
            select(HumanDecision).join(Finding).where(Finding.claim_id.in_(ids)),
        ),
    ]:
        for record in s.scalars(query):
            if not record.data.get("demo_archived"):
                record.data = {**record.data, "demo_archived": True}
    seeded = []
    for c in claims:
        if re.fullmatch(r"CG0(?:0[1-9]|[1-4][0-9]|50)", c.id):
            if c.data.get("ground_truth", {}).get("category") == "missing_evidence":
                for d in s.scalars(
                    select(Document).where(
                        Document.claim_id == c.id, Document.kind == "operative_report"
                    )
                ):
                    s.delete(d)
            for f in s.scalars(select(Finding).where(Finding.claim_id == c.id)):
                f.data = {
                    k: v
                    for k, v in f.data.items()
                    if k
                    not in [
                        "review_disposition",
                        "review_reason",
                        "reviewer",
                        "reviewed_at",
                    ]
                }
                f.status = "OPEN"
            for t in s.scalars(select(Task).where(Task.claim_id == c.id)):
                t.status = "OPEN"
                t.data = {
                    "owner": "Hospital Claims Desk",
                    "required": "operative_report",
                    "created_at": now(),
                }
            s.flush()
            analyse(s, c, record_runs=False, record_audit=False)
            for index, name in enumerate(AGENTS):
                rid = f"BASELINE-{c.id}-{index}"
                run = s.get(AgentRun, rid)
                if not run:
                    run = AgentRun(id=rid, claim_id=c.id, agent=name, data={})
                    s.add(run)
                run.data = {
                    "status": "COMPLETED",
                    "mode": "Deterministic baseline summary",
                    "duration_ms": 0,
                    "inputs_summary": f"Restored synthetic case {c.id}",
                    "tools": TOOLS[name],
                    "output": {"readiness": c.readiness, "state": c.status},
                    "next_transition": AGENTS[index + 1] if index < 7 else c.status,
                    "baseline": True,
                }
            seeded.append(c.id)
        elif not c.data.get("demo_archived"):
            c.data = {**c.data, "demo_archived": True}
            audit(
                s,
                c,
                a["role"],
                "DEMO_INTAKE_ARCHIVED",
                history_retained=True,
                demo_archived=True,
            )
    for item in s.scalars(select(Intake).where(Intake.org_id == a["org_id"])):
        item.status = "ARCHIVED"
    audit(
        s,
        s.get(Claim, "CG021"),
        a["role"],
        "DEMO_PRESENTATION_RESET",
        history_archived=True,
        restored_claims=len(seeded),
    )
    s.commit()
    return {
        "restored_claims": len(seeded),
        "scenarios": ["CG001", "CG021", "CG030", "CG048"],
        "history_retained": True,
        "message": "All 50 seeded claims restored. Tasks and human decisions reset; prior presentation history and extra intakes archived.",
    }


@router.post("/demo/reset-all")
def reset_presentation(
    a=Depends(actor),
    s=Depends(session, scope="function"),
    guard=Depends(require_reset_key),
):
    permitted(a, WRITE)
    from .main import LOCK

    with LOCK:
        result = reset_demo(s, a)
        event(
            "demo_reset",
            actor_role=a["role"],
            restored_claims=result["restored_claims"],
        )
        return result


@router.get("/demo/preflight")
def preflight(a=Depends(actor), s=Depends(session, scope="function")):
    expected = {
        "CG001": ("READY", 98),
        "CG021": ("NEEDS_RESOLUTION", 63),
        "CG030": ("HUMAN_REVIEW", 86),
        "CG048": ("INVESTIGATION", 95),
    }
    failures = []
    cases = s.scalars(select(Claim).where(Claim.org_id == a["org_id"])).all()
    visible = [c for c in cases if not c.data.get("demo_archived")]
    if len(visible) != 50:
        failures.append(
            f"Expected 50 visible claims; found {len(visible)}. Reset presentation."
        )
    for cid, (state, score) in expected.items():
        c = next((c for c in visible if c.id == cid), None)
        if not c or (c.status, c.readiness) != (state, score):
            failures.append(f"{cid} must be {score}% {state}. Reset presentation.")
    sources = retrieve(s, a, "operative report anaesthesia package", "2026-10-02")
    if not {"DOC-4.2", "PKG-6.1"} <= {x["id"] for x in sources}:
        failures.append("Required active demo knowledge is unavailable.")
    reset_available = os.getenv("DEMO_MODE", "true") == "true" and a["role"] in WRITE
    if not reset_available:
        failures.append("Demo reset is unavailable for this mode/role.")
    jobs = s.scalars(
        select(AnalysisJob)
        .join(Claim)
        .where(
            Claim.org_id == a["org_id"], AnalysisJob.status.in_(["QUEUED", "RUNNING"])
        )
    ).all()
    if jobs:
        failures.append("Analysis jobs are still running; wait before reset.")
    return {
        "status": "DEMO READY" if not failures else "NOT READY",
        "failures": failures,
        "database": "SQLite"
        if s.bind.dialect.name == "sqlite"
        else s.bind.dialect.name,
        "schema_version": max(s.scalars(select(Migration.version))),
        "visible_claims": len(visible),
        "reset_available": reset_available,
        "reset_check": "Read-only availability check; mutation correctness verified by regression tests.",
    }
