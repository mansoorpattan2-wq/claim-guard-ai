import os, secrets, threading, re, time
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from .db import (
    Session,
    migrate,
    Claim,
    Document,
    Finding,
    Task,
    Audit,
    AgentRun,
    HumanDecision,
    KnowledgeChunk,
    Migration,
    engine,
)
from .engine import seed, analyse, audit, now, digest, AGENTS
from .config import APP_ENV, ALLOWED_ORIGINS, validate
from .logging_config import event

TOKENS = {}
LOCK = threading.RLock()
ROLES = [
    "Claims Executive",
    "Claims Manager",
    "Medical Reviewer",
    "Integrity Investigator",
    "Payer Reviewer",
    "Administrator",
    "Auditor",
]
WRITE = {"Claims Executive", "Claims Manager"}
REVIEW = {"Claims Manager", "Medical Reviewer", "Payer Reviewer"}


@asynccontextmanager
async def lifespan(app):
    validate()
    try:
        if APP_ENV != "production":
            migrate()
        with Session() as s:
            versions = set(s.scalars(select(Migration.version)))
            if versions != {1, 2, 3}:
                raise RuntimeError("Schema v3 required. Run manage.py migrate.")
            if APP_ENV != "production":
                seed(s)
                from .p1 import bootstrap
                from .p2 import bootstrap as bootstrap_p2

                bootstrap(s)
                bootstrap_p2(s)
            else:
                from .p1 import recover_jobs

                recover_jobs(s)
        event(
            "startup", database=engine.dialect.name, app_env=APP_ENV, schema_version=3
        )
    except Exception as exc:
        event("startup_failed", error_type=type(exc).__name__)
        raise RuntimeError(
            "Database startup failed. Verify DATABASE_URL and run explicit migrations/seeding."
        ) from None
    yield
    engine.dispose()


app = FastAPI(title="ClaimGuard AI", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-Demo-Reset-Key"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        event("api_failed", method=request.method, error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"detail": "Service unavailable. Retry or request manual review."},
        )
    route = request.scope.get("route")
    event(
        "api_request",
        method=request.method,
        route=getattr(route, "path", "unmatched"),
        status=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return response


def require_reset_key(request: Request):
    expected = os.getenv("DEMO_RESET_KEY", "")
    if APP_ENV == "production" or expected:
        supplied = request.headers.get("X-Demo-Reset-Key", "")
        if not expected or not secrets.compare_digest(expected, supplied):
            raise HTTPException(
                403,
                "Presenter reset requires the deployment reset key. Use the authorized reset script.",
            )


def session():
    with Session() as s:
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise


def actor(request: Request):
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    if token not in TOKENS:
        raise HTTPException(401, "Select a demo role to establish a session.")
    return TOKENS[token]


def permitted(a, roles):
    if a["role"] not in roles:
        raise HTTPException(403, "Your demo role does not permit this action.")


def claim(s, id, a):
    c = s.get(Claim, id)
    if not c or c.org_id != a["org_id"]:
        raise HTTPException(404, "Claim not found.")
    return c


def row(x):
    return {c.name: getattr(x, c.name) for c in x.__table__.columns}


def passport(s, c):
    return {
        **row(c),
        "findings": [
            row(x) for x in s.scalars(select(Finding).where(Finding.claim_id == c.id))
        ],
        "documents": [
            row(x) for x in s.scalars(select(Document).where(Document.claim_id == c.id))
        ],
        "tasks": [row(x) for x in s.scalars(select(Task).where(Task.claim_id == c.id))],
        "runs": [
            row(x)
            for x in sorted(
                s.scalars(select(AgentRun).where(AgentRun.claim_id == c.id)),
                key=lambda run: (
                    run.data.get("started_at", run.data.get("timestamp", "")),
                    AGENTS.index(run.agent) if run.agent in AGENTS else len(AGENTS),
                    run.id,
                ),
            )
            if not x.data.get("demo_archived")
        ],
        "decisions": [
            row(x)
            for x in s.scalars(
                select(HumanDecision)
                .join(Finding, HumanDecision.finding_id == Finding.id)
                .where(Finding.claim_id == c.id)
            )
            if not x.data.get("demo_archived")
        ],
        "model_label": "Prototype operational readiness model; not probability of approval.",
    }


class RoleBody(BaseModel):
    role: str


@app.post("/api/session")
def login(b: RoleBody):
    if os.getenv("DEMO_MODE", "true") != "true":
        raise HTTPException(403, "Demo sessions are disabled.")
    if b.role not in ROLES:
        raise HTTPException(422, "Unknown demo role.")
    token = secrets.token_urlsafe(32)
    TOKENS[token] = {"role": b.role, "org_id": "demo-hospital", "id": "demo-" + b.role}
    return {"token": token, **TOKENS[token]}


@app.get("/api/health")
@app.get("/health")
def health():
    return {"status": "ok", "mode": "synthetic demo", "provider": "deterministic"}


@app.get("/ready")
@app.get("/api/ready")
def ready():
    try:
        with Session() as s:
            s.execute(text("SELECT 1"))
            if set(s.scalars(select(Migration.version))) != {1, 2, 3}:
                return JSONResponse(
                    status_code=503,
                    content={"status": "not ready", "reason": "Schema v3 required."},
                )
        return {"status": "ready", "database": engine.dialect.name, "schema_version": 3}
    except Exception as exc:
        event("database_unavailable", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": "Database unavailable."},
        )


@app.get("/api/claims")
def claims(a=Depends(actor), s=Depends(session, scope="function")):
    return [
        row(x)
        for x in s.scalars(
            select(Claim).where(Claim.org_id == a["org_id"]).order_by(Claim.id)
        )
        if not x.data.get("demo_archived")
    ]


@app.get("/api/claims/{id}")
def get_claim(id: str, a=Depends(actor), s=Depends(session, scope="function")):
    return passport(s, claim(s, id, a))


@app.get("/api/claims/{id}/passport")
def export(id: str, a=Depends(actor), s=Depends(session, scope="function")):
    c = claim(s, id, a)
    audit(s, c, a["role"], "PASSPORT_EXPORTED")
    return passport(s, c)


@app.get("/api/claims/{id}/findings")
def findings(id: str, a=Depends(actor), s=Depends(session, scope="function")):
    claim(s, id, a)
    return [row(x) for x in s.scalars(select(Finding).where(Finding.claim_id == id))]


@app.post("/api/claims/{id}/analyse")
def run(id: str, a=Depends(actor), s=Depends(session, scope="function")):
    permitted(a, WRITE)
    c = claim(s, id, a)
    analyse(s, c)
    s.flush()
    return passport(s, c)


@app.get("/api/audit")
def events(
    claim_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
    include_history: bool = False,
    a=Depends(actor),
    s=Depends(session, scope="function"),
):
    q = select(Audit).where(Audit.org_id == a["org_id"])
    if claim_id:
        claim(s, claim_id, a)
        q = q.where(Audit.claim_id == claim_id)
    q = q.order_by(Audit.timestamp.desc())
    if not include_history:
        q = q.where(Audit.data["demo_archived"].as_boolean().is_not(True))
    if limit:
        q = q.limit(limit)
    return [row(x) for x in s.scalars(q)]


@app.get("/api/resolutions")
def tasks(a=Depends(actor), s=Depends(session, scope="function")):
    return [
        row(x)
        for x in s.scalars(
            select(Task)
            .join(Claim)
            .where(
                Claim.org_id == a["org_id"],
                Claim.data["demo_archived"].as_boolean().is_not(True),
            )
        )
    ]


def task(s, id, a):
    t = s.get(Task, id)
    if not t:
        raise HTTPException(404, "Task not found.")
    return t, claim(s, t.claim_id, a)


@app.post("/api/findings/{id}/resolve")
def resolve(id: str, a=Depends(actor), s=Depends(session, scope="function")):
    permitted(a, WRITE)
    f = s.get(Finding, id)
    if not f:
        raise HTTPException(404, "Finding not found.")
    c = claim(s, f.claim_id, a)
    if f.rule != "F14":
        raise HTTPException(
            422, "This finding requires human review, not document resolution."
        )
    t = s.get(Task, f"RT-{c.id}")
    audit(s, c, a["role"], "RESOLUTION_OPENED", finding_id=f.id)
    return row(t)


class ActionBody(BaseModel):
    action: str


@app.post("/api/resolutions/{id}/request")
def request_document(
    id: str, b: ActionBody, a=Depends(actor), s=Depends(session, scope="function")
):
    permitted(a, WRITE)
    t, c = task(s, id, a)
    if t.status == "COMPLETED":
        raise HTTPException(409, "Task is already complete.")
    if b.action not in ["generate", "simulate_send"]:
        raise HTTPException(422, "Unknown request action.")
    if b.action == "simulate_send" and not t.data.get("request"):
        raise HTTPException(409, "Generate and review the request first.")
    text = f"To: Hospital Claims Desk\nPlease provide the existing signed operative report for {c.id}, {c.patient}, {c.procedure}, service date 2026-10-02. Include the beneficiary identifier, procedure, service date and signature. Do not create or alter clinical content.\nSynthetic demo request only."
    t.data = {**t.data, "request": text}
    t.status = "REQUESTED" if b.action == "simulate_send" else "DRAFTED"
    audit(
        s,
        c,
        a["role"],
        "REQUEST_SIMULATED" if b.action == "simulate_send" else "REQUEST_GENERATED",
        task_id=id,
        external_delivery=False,
    )
    return row(t)


@app.post("/api/resolutions/{id}/simulate-response")
def simulate(id: str, a=Depends(actor), s=Depends(session, scope="function")):
    permitted(a, WRITE)
    t, c = task(s, id, a)
    if t.status != "REQUESTED":
        raise HTTPException(409, "Simulate sending the request first.")
    text = f"SYNTHETIC OPERATIVE REPORT — DEMONSTRATION ONLY\nClaim: {c.id}\nBeneficiary: {c.patient}\nProcedure: {c.procedure}\nService date: 2026-10-02\nSigned by: {c.data['doctor']}\nExisting synthetic report supplied in response to the evidence request."
    t.data = {**t.data, "response": text}
    t.status = "RECEIVED"
    audit(
        s,
        c,
        a["role"],
        "RESPONSE_RECEIVED",
        task_id=id,
        source="synthetic demo adapter",
    )
    return row(t)


class ResponseBody(BaseModel):
    text: str = Field(min_length=40, max_length=100000)


@app.post("/api/resolutions/{id}/response")
def upload_response(
    id: str, b: ResponseBody, a=Depends(actor), s=Depends(session, scope="function")
):
    permitted(a, WRITE)
    t, c = task(s, id, a)
    if t.status not in ["REQUESTED", "RECEIVED"]:
        raise HTTPException(409, "Send the request before receiving evidence.")
    t.data = {**t.data, "response": b.text}
    t.status = "RECEIVED"
    audit(
        s, c, a["role"], "RESPONSE_RECEIVED", task_id=id, source="text document upload"
    )
    return row(t)


@app.post("/api/resolutions/{id}/complete")
def complete(id: str, a=Depends(actor), s=Depends(session, scope="function")):
    permitted(a, WRITE)
    with LOCK:
        t, c = task(s, id, a)
        if t.status == "COMPLETED":
            return passport(s, c)
        if t.status != "RECEIVED":
            raise HTTPException(409, "Receive a document before validation.")
        text = t.data.get("response", "")
        required = {
            "Claim": c.id,
            "Beneficiary": c.patient,
            "Procedure": c.procedure,
            "Service date": "2026-10-02",
        }
        exact = all(
            re.findall(r"^" + re.escape(key) + r":\s*([^\r\n]+)", text, re.M) == [value]
            for key, value in required.items()
        )
        signatures = re.findall(r"^Signed by:[ \t]*([^\r\n]+)", text, re.M)
        if (
            not exact
            or "operative report" not in text.lower()
            or len(signatures) != 1
            or not signatures[0].strip()
        ):
            audit(
                s,
                c,
                "Resolution validator",
                "VALIDATION_FAILED",
                task_id=id,
                reason="Identity, procedure, service date, report type or signature missing",
            )
            s.commit()
            raise HTTPException(
                422,
                "Validation failed: the operative report must match claim, beneficiary, procedure and service date, and include a signature. No readiness change was made.",
            )
        did = f"{c.id}-resolved-operative"
        if not s.get(Document, did):
            s.add(
                Document(
                    id=did,
                    claim_id=c.id,
                    kind="operative_report",
                    title="Signed operative report",
                    text=text,
                    hash=digest(text),
                    data={
                        "validated": True,
                        "page": 1,
                        "version": "1.0",
                        "timestamp": now(),
                        "source": "resolution response",
                    },
                )
            )
        s.flush()
        before = c.readiness
        audit(
            s,
            c,
            "Resolution validator",
            "DOCUMENT_VALIDATED",
            task_id=id,
            document_id=did,
            hash=digest(text),
        )
        rerun_started = time.perf_counter()
        analyse(s, c, targeted=True)
        rerun_ms = round((time.perf_counter() - rerun_started) * 1000, 2)
        t.status = "COMPLETED"
        t.data = {
            **t.data,
            "completed_at": now(),
            "before": before,
            "after": c.readiness,
            "rerun_duration_ms": rerun_ms,
        }
        audit(
            s,
            c,
            a["role"],
            "RESOLUTION_COMPLETED",
            previous_readiness=before,
            new_readiness=c.readiness,
            rerun_duration_ms=rerun_ms,
            task_id=id,
        )
        s.commit()
        return passport(s, c)


class DecisionBody(BaseModel):
    decision: str
    reason: str = Field(min_length=3, max_length=2000)


@app.post("/api/findings/{id}/decision")
def decision(
    id: str, b: DecisionBody, a=Depends(actor), s=Depends(session, scope="function")
):
    permitted(a, REVIEW)
    f = s.get(Finding, id)
    if not f:
        raise HTTPException(404, "Finding not found.")
    c = claim(s, f.claim_id, a)
    if b.decision not in ["AGREE", "INCORRECT", "SPECIALIST"]:
        raise HTTPException(422, "Unknown decision.")
    s.add(
        HumanDecision(
            id=str(uuid4()),
            finding_id=id,
            data={
                "decision": b.decision,
                "reason": b.reason,
                "reviewer": a["role"],
                "timestamp": now(),
            },
        )
    )
    audit(
        s,
        c,
        a["role"],
        "HUMAN_DECISION",
        finding_id=id,
        decision=b.decision,
        reason=b.reason,
    )
    return {"saved": True, "message": "Decision recorded; original finding retained."}


@app.get("/api/knowledge/sources")
def knowledge(a=Depends(actor), s=Depends(session, scope="function")):
    return [
        row(x)
        for x in s.scalars(
            select(KnowledgeChunk).where(KnowledgeChunk.org_id == a["org_id"])
        )
    ]


@app.post("/api/demo/reset")
def reset(
    a=Depends(actor),
    s=Depends(session, scope="function"),
    guard=Depends(require_reset_key),
):
    permitted(a, WRITE)
    if os.getenv("DEMO_MODE", "true") != "true":
        raise HTTPException(403, "Demo reset disabled.")
    with LOCK:
        c = claim(s, "CG021", a)
        for d in s.scalars(
            select(Document).where(
                Document.claim_id == c.id, Document.kind == "operative_report"
            )
        ):
            s.delete(d)
        t = s.get(Task, "RT-CG021")
        t.status = "OPEN"
        t.data = {
            "owner": "Hospital Claims Desk",
            "required": "operative_report",
            "created_at": now(),
        }
        s.flush()
        analyse(s, c)
        audit(s, c, a["role"], "DEMO_SCENARIO_RESET")
        s.commit()
    return passport(s, c)


from .p1 import router as p1_router

app.include_router(p1_router)
from .p2 import router as p2_router

app.include_router(p2_router)
