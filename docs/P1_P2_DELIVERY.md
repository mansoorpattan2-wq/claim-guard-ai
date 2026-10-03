> Historical phase record. PostgreSQL/Docker was subsequently verified locally; see [POSTGRES_MIGRATION.md](POSTGRES_MIGRATION.md) and [DEPLOYMENT.md](DEPLOYMENT.md). Public deployment remains unverified.

# ClaimGuard AI — P1 and selected P2 delivery

Implemented 3 October 2026. P0 remains the regression contract: the original 13 backend tests and three browser tests are retained unchanged. The CG021 evidence requirement, request, response validation, targeted reruns and 63% → 94% READY transition remain intact.

## Completed features

1. **New Claim Intake:** drag/drop and multi-file picker, actual upload progress, automatic classification and correction, extracted identity preview with conflicting values surfaced, explicit identity confirmation, Analyse Claim, persisted eight-stage progress, failed-job retry, completed Passport link. A separate demo tab opens CG001, CG021, CG030 and CG048. Original upload bytes are retained under opaque names in local storage.
2. **Human Review:** org-scoped queue, finding details, linked evidence viewer, Agree / Override / Request Information / Escalate, mandatory override reason, persisted HumanDecision including original finding/source snapshot, AuditEvent for each action. Billing overrides recalculate readiness/state and survive analysis reruns; required missing-operative evidence cannot be overridden through this workspace.
3. **Agent Trace:** check name, status, start/end, measured job duration, input summary/hash, tools, evidence/finding references, structured output, concise rationale and next transition. Job failures and retries are retained. Interrupted jobs/runs are marked FAILED on restart and claims require human review. Accepted synchronous P0 runs are labelled recorded summaries; their zero-duration metadata is not presented as measured execution. No chain-of-thought is displayed.
4. **Knowledge Center:** synthetic source authority, version, effective/expiry dates, active/superseded status and chunk count; date-filtered retrieval with ranked passages, overlap scores, metadata and bounded grounded answer. Judge question: “Is anaesthesia separately billable for demo package LAP-APP-01?” Unsupported or out-of-date retrieval returns human-review/insufficient-evidence state.
5. **Printable Claim Readiness Passport:** standalone HTML download plus browser Print / Save PDF. Includes summary, readiness, checks, unresolved findings, citations, human decisions, source hashes/provenance and UTC generation time. User text is escaped. Existing JSON export remains available.
6. **Investigation Graph:** SQL-backed connected projection for CG045–CG050, Hospital → Doctor → Procedure → Claims → Documents. Click/keyboard selection, claim focus, zoom/reset, source details, linked Passports. Signals: six identical diagnostic SHA-256 fingerprints; 15 invoice-template pairs at similarity ≥ 0.90 after identity labels are removed; seeded provider frequency 6/6 versus 34/44; CG048's explicit fictional prior procedure 12 days earlier versus a demo 30-day threshold. Every signal is an **INVESTIGATION LEAD**, with common-template/small-sample limitations stated. Mobile uses signal cards and linked claims; full graph is desktop.
7. **Synthetic FHIR import:** load/upload/download one sample Bundle, validate its narrow supported contract, map to Intake/IntakeFile/Claim/Document, run the same analysis pipeline, open its 98% READY Passport. Source mapping and import are audited.
8. **Integrations:** truthful FHIR, NHCX, HIS/HMIS, object storage, notifications and webhooks cards. FHIR and filesystem probe buttons test real local adapters; disconnected services cannot be “tested” as connected.
9. **UX and reliability:** existing navy/teal visual system retained; source hierarchy, readable graph labels, responsive layouts, focused controls, loading/error/empty states and reduced-motion support. Visible Reset presentation remounts new workspaces and restores all four stories.

## Routes

| Page | Behavior |
|---|---|
| `/claims/new` | Working intake and four-scenario demo loader |
| `/review` | Human review workspace |
| `/knowledge` | Source catalog and retrieval test |
| `/investigations` | Connected investigation graph |
| `/integrations` | Adapter status and FHIR import |
| `/claims/{id}/passport` | Printable Passport preview/export |
| `/claims/{id}` → Agent Trace | Expanded persisted trace |

These replace placeholders or extend existing route patterns; dashboard, claims, resolution, evidence and audit routes are preserved. `/admin` remains a clearly identified later capability.

New backend endpoints (all prefixed `/api`):

| Method | Route |
|---|---|
| POST | `/intakes` |
| GET | `/intakes/{id}` |
| POST | `/intakes/{id}/files` |
| POST | `/intakes/{id}/files/{file_id}/classification` |
| POST | `/intakes/{id}/analyse` |
| GET | `/analysis-jobs/{id}` |
| POST | `/analysis-jobs/{id}/retry` |
| GET | `/review` |
| POST | `/review/{id}/decision` |
| GET | `/knowledge/catalog` |
| POST | `/knowledge/retrieve` |
| GET | `/claims/{id}/printable` |
| GET | `/investigations/graph` |
| GET | `/integrations/fhir/sample` |
| POST | `/integrations/fhir/import` |
| GET | `/integrations` |
| POST | `/integrations/{id}/test` |
| POST | `/demo/reset-all` |

The existing `/api/audit` adds optional `limit=1..500`; omitting it retains complete-history behavior. The UI requests 200 recent events and labels that limit.

## Database and architecture

The existing Next.js/TypeScript frontend, FastAPI service, SQLAlchemy persistence, rules/readiness engine, evidence viewer and CG021 resolution components are reused. P1 and P2 backend routers live in `backend/app/p1.py` and `p2.py`; printable rendering in `printable.py`. New React workspaces and trace/export components sit alongside the accepted components. No new cloud service is needed.

Schema migration v2 adds:

- `intakes`: id, org FK, optional claim FK, status, JSON identity/job/provenance metadata.
- `intake_files`: id, intake FK, kind, extracted text, JSON filename/hash/storage/extraction metadata.
- `analysis_jobs`: id, claim FK, status, JSON persisted steps/timestamps/errors.
- `knowledge_sources`: id, org FK, title, status, JSON authority/version/date/chunk metadata.

Schema migration v3 adds `procedure_history`: id, org/claim FKs, patient, procedure, service_date and JSON fictional-registry provenance. Migrations are idempotent `checkfirst` additions. Existing Claim, Document, Finding, Task, HumanDecision, AgentRun, Audit and KnowledgeChunk tables remain in use. P1 metadata additions use their existing JSON fields; no P0 columns are removed. Fresh startup reaches schema v3 automatically; existing schema v1 advances without deleting data.

The complete reset restores the 50 seeded cases, removes simulated missing-report responses, rebuilds original findings/tasks/readiness, archives extra intake/FHIR claims and intakes, and archives historical source-linked decisions, agent runs and audit history. The hardening release clears these records from the active presentation while retaining them in storage; historical audit is available with include_history=true. It refuses to reset while analysis jobs are active. CG021's original single-case reset endpoint/button remains available. No database-file deletion is needed.

## Agents and tools

Eight deterministic execution nodes are reused and extended: Reading documents; Validating eligibility; Checking evidence; Retrieving policy; Checking clinical consistency; Checking billing; Checking integrity signals; Preparing Claim Passport.

Tools: TXT/PDF/DOCX extraction, classification/field parser, SHA-256, policy/date comparisons, document inventory, org/date-filtered keyword retrieval, identity comparison, arithmetic/package rules, org-scoped fingerprint/provider queries, readiness hard gates and audit writer. Graph adds difflib invoice-template similarity and explicit prior-procedure lookup. FHIR adds bounded JSON/base64 parsing and local resource-reference mapping. The original CG021 targeted rerun still executes its four relevant checks. No model key is required.

## Demo adapters and limits

- All beneficiaries, providers, histories and policy wording are fictional. Readiness is an operational prototype score; humans retain consequential decisions.
- No live LLM, vector database, OCR or Neo4j. Keyword retrieval and graph calculations operate on persisted SQL data. This is a deterministic execution pipeline rather than a live model-agent service.
- TXT must be UTF-8; PDF must have extractable text; DOCX paragraphs are parsed. PNG/JPEG and scanned PDFs remain unreadable and trigger human review. Limits: 20 files/intake, 2 MB/file, 30 PDF pages, 4 MB expanded DOCX.
- Uploaded intake supports Laparoscopic appendectomy / LAP-APP-01 only. Confirmed claim totals are represented as one package line; arbitrary invoice line extraction is not implemented. Seeded CG030 demonstrates the separate anaesthesia billing rule.
- FHIR is a **Demo Adapter** for a synthetic R4 collection Bundle: one Patient, Coverage and Claim, Organization references, text/plain DocumentReference/Binary, one LAP-APP-01 procedure/package line, whole-rupee INR. Only in-bundle references are resolved; no remote fetch. Checks include identity/coverage references, dates, totals/currency and base64 evidence. This is not a full FHIR validator, certification, NHCX profile validator, submission transport or adjudication service. Mapping references: [FHIR R4 Bundle](https://hl7.org/fhir/R4/bundle.html), [Claim](https://hl7.org/fhir/R4/claim.html), [DocumentReference](https://hl7.org/fhir/R4/documentreference.html).
- FHIR and local filesystem storage: **Demo Adapter**. Notifications: **Demo Adapter**, in-app/audit and simulated requests only. NHCX, HIS/HMIS and webhooks: **Not Connected**. No emails or hospital messages are sent.
- Demo-role sessions are in memory and must be reconnected after a backend restart. Production identity, tenant provisioning, retention controls and administration are outside this release. Storage is local; no S3 adapter.
- SQLite was exercised; optional PostgreSQL configuration is retained but untested here. Jobs execute in the local process; interruption is recorded and requires explicit retry.
- Print / Save PDF uses the browser dialog, not server-side PDF rendering. The exported standalone HTML contains the complete report; the embedded preview scrolls.

## Inspect and rehearse

Use [DEMO.md](DEMO.md) for the exact four-minute sequence and [VERIFICATION.md](VERIFICATION.md) for checks. Inspect the live pages above and screenshots: `claim-passport-desktop.png`, `evidence-viewer-desktop.png`, `intake-analysis-desktop.png`, `review-workspace-desktop.png`, `knowledge-desktop.png`, `printable-passport-desktop.png`, `investigation-graph-desktop.png`, `fhir-integrations-desktop.png`, `investigation-mobile.png`.

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
powershell -ExecutionPolicy Bypass -File .\reset-demo.ps1
```

Open `http://127.0.0.1:3000/dashboard`. Reset requires the running backend; it can also be done using the visible Reset presentation button as Claims Executive or Claims Manager. Offline reset with services stopped: `python backend/manage.py reset-demo`.
