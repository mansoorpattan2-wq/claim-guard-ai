> Historical phase record. PostgreSQL/Docker was subsequently verified locally; see [POSTGRES_MIGRATION.md](POSTGRES_MIGRATION.md) and [DEPLOYMENT.md](DEPLOYMENT.md). Public deployment remains unverified.

# Current frozen release

This document records the accepted P0 architecture. See [P1/P2 delivery](P1_P2_DELIVERY.md) for the additive routes and schema v2/v3; [technical defense](TECHNICAL_DEFENSE.md) describes the frozen implementation and [limitations](LIMITATIONS.md) records its verified scope.

# ClaimGuard AI — P0 architecture and implementation record

The initial workspace was empty. No existing code was replaced. The DOCX and pasted master build brief were read as product specifications; the user's explicit P0 instruction governs scope. The architecture and three demo scenarios were presented before implementation.

## Repository

```text
frontend/
  src/app/                  Next.js routing, locally bundled fonts, design tokens
  src/components/           Responsive workspace and evidence viewer
  src/lib/api.ts            Typed API client, central permission helpers
  tests/p0.spec.ts          Browser regressions against running services
backend/
  app/db.py                 SQLAlchemy relational models and initial schema revision
  app/engine.py             Scoring, hard gates, source selection, synthetic seed
  app/main.py               Validated FastAPI routes, server RBAC, transactions
  tests/                    Isolated database and API regression suite
  run.py / manage.py        Service and migration/seed entry points
docs/                       Architecture, demo script, captured screens
start.ps1                   Minimal local Windows startup
compose.yaml                Optional PostgreSQL development database
```

## P0 database model

Organisation → Claim → Document, Finding, ResolutionTask, AgentRun, AuditEvent. Finding → HumanDecision. Organisation → KnowledgeChunk. An initial schema revision is recorded in `schema_migrations`.

Patient aliases, policy attributes, billing line items, score breakdowns and synthetic ground truth are stored in structured claim JSON for this P0. Evidence objects are immutable source snapshots embedded in finding JSON. Source metadata accompanies each knowledge chunk. These are deliberately consolidated prototype representations; separate Patient, Policy, LineItem, EvidenceObject, KnowledgeSource, consent and user-membership tables belong to a later schema revision. The complete production entity list in the brief is not represented as empty tables.

SQLite provides the tested persistent local path. SQLAlchemy and the included psycopg driver support a PostgreSQL connection URL. Docker/PostgreSQL execution has not been verified in this environment. `manage.py migrate` applies the versioned initial schema; `manage.py seed` is idempotent. Future column evolution requires explicit incremental migrations, rather than extending `create_all`.

## Route map

| Web route | Behavior |
| --- | --- |
| `/`, `/dashboard` | Computed metrics, attention queue, demo links, recent events |
| `/claims` | Search, status filter, sorting and pagination |
| `/claims/new` | Clearly labelled seeded demo intake adapter |
| `/claims/[id]` | Passport, score breakdown, findings, evidence, trace, decisions, audit |
| `/claims/[id]/evidence/[findingId]` | Finding and highlighted effective policy source; human disposition |
| `/resolutions` | Persistent tasks and controlled evidence-response workflow |
| `/audit` | Searchable org-scoped event history |
| `/review`, `/knowledge` | Explicit P1 notices, links to working P0 capability |
| `/investigations`, `/integrations`, `/admin` | Explicit P2 notices; linked integrity evidence remains available |

API: `POST /api/session`; `GET /api/health`; `GET /api/claims`; `GET /api/claims/{id}`; `GET /api/claims/{id}/passport`; `GET /api/claims/{id}/findings`; `POST /api/claims/{id}/analyse`; `GET /api/resolutions`; `POST /api/findings/{id}/resolve`; `POST /api/resolutions/{id}/request`; `POST /api/resolutions/{id}/simulate-response`; `POST /api/resolutions/{id}/response`; `POST /api/resolutions/{id}/complete`; `POST /api/findings/{id}/decision`; `GET /api/audit`; `GET /api/knowledge/sources`; `POST /api/demo/reset`.

## Frozen P0 sequence and result

1. Persistent schema and 50-claim seed with the specified 20/8/7/5/4/6 categories.
2. Rules-based checks and versioned synthetic source citations.
3. CG021 request → receipt → validation → targeted rerun → score/state update.
4. Responsive shell, overview, claims queue and passport.
5. Source viewer, role-restricted human disposition, JSON export.
6. Audit, resets and real API/browser regression checks.

All six steps are implemented. Full upload/OCR/FHIR intake, LangGraph, provider-backed LLM synthesis, semantic pgvector retrieval and Neo4j remain later scope. P0 uses an explicitly labelled deterministic orchestrator and rule-ID source retrieval with effective-date filtering. It does not claim to run semantic/vector RAG or external services. Service failures and absent applicable sources route to human review.

## Scoring contract

Weights: eligibility 20; documentation 25; policy 20; clinical consistency 15; billing 15; integrity/data quality 5. A baseline synthetic claim receives 3/5 integrity/data quality points, yielding 98. Missing surgical evidence receives 6/25 documentation and 3/15 clinical points; a hard gate caps readiness at 63 and prevents READY. CG021 carries a declared prototype billing reserve of 4 points after evidence arrives; its complete passport therefore scores 94. These are prototype assumptions, not calibrated approval probabilities.

Inactive eligibility caps readiness at 49. Identity conflict caps it at 39. An applicable source failure gives policy zero and forces HUMAN_REVIEW, capped at 49. Document reuse is calculated from SHA-256 fingerprints across distinct beneficiaries inside the same organisation; provider ratios are calculated from the seeded claims. Signals produce investigation leads, never guilt or denial.

## Resolution transaction

`OPEN → DRAFTED → REQUESTED → RECEIVED → COMPLETED`.

Generation produces a reviewable request, with simulated delivery explicitly identified. A response must contain exactly one matching claim ID, beneficiary, procedure and service-date field, an operative-report type marker, and a nonempty signature field. Conflicting duplicate identity fields fail validation. This validates structured text, not medical authenticity or a cryptographic signature. Failed validation is audited and makes no score change.

Successful completion attaches the hashed source document and reruns intake validation, evidence, clinical consistency and passport synthesis. Billing/eligibility agent runs are preserved. Task completion, finding resolution, updated score/state and audit events are committed together. A repeated completion is idempotent. A process lock serializes demo completion; production multi-worker coordination requires database row locking or a job system.

## Demo access and production boundaries

The unauthenticated role selector intentionally creates org-scoped demo sessions. Backend permission checks protect writes and decisions. Sessions are in-memory and renewed after a backend restart. Auditor access is read-only except for auditable export. Original findings and source snapshots remain available after human decisions.

This is a local synthetic-data demo, not production authentication. Production requires identity-provider login, expiring secure sessions, claim assignment/purpose grants, consent enforcement, encrypted storage/transport, malware scanning, governed policy approval, retention, append-only external audit storage and authentic document verification. No NHCX/HIS/notification integration is represented as live. No real patient data or external messages are used.
# Current frozen release

This document records the accepted P0 architecture. See [P1/P2 delivery](P1_P2_DELIVERY.md) for the additive routes and schema v2/v3; [technical defense](TECHNICAL_DEFENSE.md) describes the frozen implementation and [limitations](LIMITATIONS.md) records its verified scope.
