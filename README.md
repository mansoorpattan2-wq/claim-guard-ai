# ClaimGuard AI

A persistent claim-readiness workspace using Next.js, TypeScript, FastAPI and SQLAlchemy. P0, P1 and the selected P2 features are implemented. CG021 remains the priority regression: cited missing-operative-report resolution, **63% → 94% READY**, targeted reruns and durable audit history.

All patients, providers, histories and policy wording are synthetic. Readiness is an operational prototype score; humans retain decision authority.

## Start and reset on Windows

Requires Node.js 20.9+ and Python 3.11+. From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
powershell -ExecutionPolicy Bypass -File .\reset-demo.ps1
powershell -ExecutionPolicy Bypass -File .\preflight-demo.ps1
```

Open **http://127.0.0.1:3000/dashboard**. API documentation: **http://127.0.0.1:8000/docs**. Start installs missing application dependencies and launches hidden local service windows; reset requires the running backend. Wait for startup if installing dependencies for the first time. Logs: `backend.log`, `backend-error.log`, `frontend.log`, `frontend-error.log`.

The visible **Reset presentation** button restores all 50 seeded cases and the four judge scenarios. It restores active human decisions and tasks, archives additional uploaded/imported claims and prior session history, and retains historical evidence and records. The button asks for confirmation. It refuses a reset while jobs are running. The original CG021 **Reset demo** button still restores that case alone. With services stopped, use `python backend/manage.py reset-demo` for an offline reset.

## Delivered workflows

- Multi-file intake, classification/correction, upload progress, identity confirmation, persisted eight-stage analysis and failed-job retry.
- Human review queue with cited evidence, Agree / Override / Request Information / Escalate, mandatory override reason, durable decisions/audit and applicable state recalculation.
- Structured agent trace with timing, tools, source references, outputs and transitions.
- Knowledge-source governance metadata and effective-date-filtered, ranked retrieval tests.
- Printable/exportable Claim Readiness Passport, standalone HTML and browser Save PDF; existing JSON export retained.
- Connected CG045–CG050 investigation graph with fingerprints, invoice similarity, frequency and fictional prior-procedure leads.
- Synthetic FHIR Bundle import into the actual intake/analysis pipeline and honest integration status/probes.
- Responsive workspaces, keyboard graph selection and full-presentation reset.

One-click scenarios: **CG001 READY 98%**, **CG021 63% → 94% READY**, **CG030 billing review 86%**, **CG048 INVESTIGATION LEAD 95%**. Demo mode offers role selection without a password. Claims Executive/Manager can resolve evidence; Medical Reviewer/Payer Reviewer/Manager can record review decisions; Auditor is read-only. API permissions enforce these controls.

## Manual setup

Run backend and frontend in separate terminals:

```powershell
python -m pip install --target backend/vendor -r backend/requirements.txt
python backend/run.py
```

```powershell
npm.cmd ci --prefix frontend
npm.cmd run dev --prefix frontend
```

SQLite is the default. Fonts are bundled; no Docker, cloud service or model key is required. Sessions are in memory: reconnect/select a role after a backend restart. The backend runner does not auto-reload source changes; restart its process after editing Python. Avoid running `next build` alongside a dev server; restart the frontend afterward if needed.

## Verified PostgreSQL deployment and SQLite recovery

The three-service Docker deployment uses PostgreSQL, a production FastAPI process and a standalone Next.js frontend on ports 15432/8100/3100. Migrations, repeated seed/reset and CG021 restart persistence are verified locally. Public cloud deployment remains unverified.

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for exact bootstrap/start/reset/preflight commands, secret variables, Vercel/Render preparation, persistent upload volumes, prototype authentication and rollback. [POSTGRES_MIGRATION.md](docs/POSTGRES_MIGRATION.md) records measured results; [DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md) separates local and public gates.

Production startup never migrates, seeds or resets. Run `python backend/manage.py migrate` and `python backend/manage.py seed` explicitly with the intended DATABASE_URL. Development startup retains automatic migration/idempotent seed. Leave DATABASE_URL unset to recover the original SQLite demo on ports 3000/8000.

## Verification

```powershell
python backend/test.py
python -m pip install --target backend/tools ruff==0.16.10
python backend/lint.py
.\backend\tools\bin\ruff.exe format --check backend/app backend/tests/test_p1.py backend/tests/test_p2.py backend/lint.py
npm.cmd run typecheck --prefix frontend
npm.cmd run lint --prefix frontend
npm.cmd run format:check --prefix frontend
npm.cmd run build --prefix frontend
```

Start both services before browser tests. Run from the repository root:

```powershell
npm.cmd exec --prefix frontend -- playwright install chromium
npm.cmd exec --prefix frontend -- playwright test --config frontend/playwright.config.ts
powershell -ExecutionPolicy Bypass -File .\reset-demo.ps1
powershell -ExecutionPolicy Bypass -File .\preflight-demo.ps1
```

Backend tests use an isolated temporary database. Browser tests exercise the running synthetic database; the seven added tests reset the complete presentation before each test. The original 13 backend and three browser regression tests are unchanged. New tests cover intake, classification, recovery/retry, review, knowledge, print export, graph, FHIR, reset and mobile/keyboard behavior. Screenshots are saved in `docs/`.

## Scope and documentation

TXT, text PDF and DOCX extraction works; unreadable images/scans require human review because OCR is not connected. New intake supports only Laparoscopic appendectomy / LAP-APP-01 and one confirmed package total. Retrieval is deterministic keyword/rule lookup; the graph is a SQL projection. FHIR supports one narrow synthetic R4 collection contract, not general validation or NHCX conformance. FHIR/local filesystem/in-app notifications are **Demo Adapter** capabilities. NHCX, HIS/HMIS and webhooks are **Not Connected**. No external messages are sent. Production identity, cloud storage and administration remain outside this release.

- [Delivery report: features, routes, schema, tools and limits](docs/P1_P2_DELIVERY.md)
- [Presenter runbook with fallback actions](docs/JUDGE_DEMO.md)
- [Technical defense and architecture](docs/TECHNICAL_DEFENSE.md)
- [Explicit limitations](docs/LIMITATIONS.md)
- [Production roadmap](docs/PRODUCTION_ROADMAP.md)
- [Verification results and screenshots](docs/VERIFICATION.md)
- [Accepted P0 architecture](docs/ARCHITECTURE.md)
