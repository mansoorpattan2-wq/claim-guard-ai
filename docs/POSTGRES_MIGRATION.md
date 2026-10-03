# PostgreSQL inspection and migration record

## Inspection before implementation

The accepted SQLite build remains the recovery baseline. No claim rules, readiness weights, seeded scenarios or UI design need to change.

- `app/db.py` uses SQLAlchemy declarative models and `DATABASE_URL` already. The psycopg binary driver is already pinned. SQLite-specific `check_same_thread` must be selected by parsed dialect, not an arbitrary string prefix. PostgreSQL needs bounded pooling, pre-ping and a connection timeout.
- The schema has 15 tables, string application-generated IDs, explicit foreign keys, integer amounts/readiness, text contents and generic SQLAlchemy JSON. Business tables have no autoincrement/server defaults, SQL boolean columns or server timestamps. PostgreSQL inspection found SQLAlchemy's implicit SERIAL/sequence default on the integer `schema_migrations.version` primary key; migrations still write explicit revision numbers. Timestamps/dates remain application-written ISO strings, including values inside JSON. Preserve these types and nullable behavior rather than introduce a data migration.
- Revision 1 currently calls `metadata.create_all`, including later tables; revisions 2/3 therefore skip already-created tables. Split initial creation into the actual P0 tables and run each revision and its version record within one transaction. PostgreSQL transactional DDL should roll back failures; do not swallow migration exceptions.
- No raw SQLite SQL appears in application queries. JSON `.as_boolean().is_not(True)` needs real PostgreSQL verification for missing keys; text JSON is otherwise read/written by SQLAlchemy. No custom secondary indexes exist in the baseline; primary-key indexes and foreign-key constraints must be inspected rather than claimed as newly implemented indexes.
- SQLAlchemy sessions commit at request completion and roll back exceptions. Several operations explicitly flush/commit. PostgreSQL enforces foreign keys that local SQLite historically did not enforce: parent/child flush ordering must be checked against the real driver.
- Seed returns early for existing CG001, with legacy backfill logic; it is not a reset. Full presentation reset archives imported claims and old history, restores 50 active claims and retains archived storage. Normal deployment startup must not call seed/migrate automatically.
- P1 bootstrap combines governed-source seeding with interrupted-job recovery. Separate job recovery from source insertion so deployment startup only recovers interrupted work, without re-seeding presentation data.
- Current process-local tokens, background jobs and `RLock` imply **one backend process / one replica**. PostgreSQL does not remove that constraint. Do not claim multi-replica safety or distributed job execution.
- Baseline test fixture always chooses temporary SQLite; add an explicit opt-in dedicated PostgreSQL test URL. The preflight test specifically asserts SQLite: retain it unchanged in the SQLite suite and report the PostgreSQL subset separately.
- Frontend already uses a same-origin `/api` proxy with server-only `API_URL`. Retain that convention so `DATABASE_URL` never reaches browser code. Configure the HTTPS backend origin at frontend build time.
- CORS has two fixed local origins; make the same setting environment-driven with explicit production origins. Demo role selection grants roles freely: role checks alone cannot protect an Internet-exposed reset. Add a server-side deployment reset secret, while preserving local demo reset behavior.
- Synthetic evidence is stored as text in the database, not external files. Original runtime upload bytes use `backend/storage` and must move behind a configurable local adapter and persistent volume. No object-store connection is implied.
- Docker is installed, but the engine was initially stopped. PostgreSQL verification is pending until real migrations, suites and backend-restart persistence succeed. Public deployment is separately pending credentials and real public URL checks.

## Verification results

Verified locally on 2026-10-03. **PostgreSQL 17.11**, official `postgres:17-alpine` container on Docker Desktop; not a managed cloud provider. SQLite is retained separately.

| Gate | Measured result |
|---|---|
| Schema v1 -> v2 -> v3 | PASS on fresh PostgreSQL; repeated migration unchanged |
| Failed revision | Deliberate v2 failure rolls back all DDL/version rows; rerun succeeds |
| Schema inspection | 15 tables / 17 foreign keys; types, nullable flags, primary keys and defaults match; generic JSON; no custom secondary indexes |
| Initial seed | Twice successful, 50 active synthetic claims, governed sources and graph/review data available |
| Initial scenarios | CG001 98 READY; CG021 63 NEEDS_RESOLUTION; CG030 86 HUMAN_REVIEW; CG048 95 INVESTIGATION |
| Mandatory persistence | CG021 63 -> 94 READY -> stop/start backend -> 94 READY; Passport/task/runs, audit and human decision metadata equal; original upload bytes retained |
| Explicit reset | Twice successful; CG021 63; exactly 50 visible initial claims; archives retained as intended |
| SQLite backend suite | **40 passed**, including all original 33 plus 7 deployment regressions |
| PostgreSQL backend suite | **39 passed**, 1 unchanged SQLite-specific test excluded; fresh disposable database per invocation |
| PostgreSQL production browser suite | **19 passed (1.7 minutes)**, all original tests/assertions retained |
| SQLite recovery browser suite | **19 passed (2.5 minutes)** after restarting the original local backend on final code |
| Three complete reset rehearsals | **3/3 passed** on final PostgreSQL container code; same expected states; no spoken narration timing claim |
| Production frontend | Docker clean npm install and standalone Next.js build PASS; strict TypeScript PASS |
| Static checks | ESLint, Prettier, baseline Ruff `F,E9` lint and changed-Python format checks PASS |
| Clean deployment | Fresh isolated DB/upload volumes -> explicit migrate -> seed -> API/frontend healthy -> DEMO READY -> complete judge browser flow PASS |
| Production bootstrap safety | Starting against unmigrated clean DB fails rather than creating/seed/resetting it |
| Secrets / permissions | Actual deployment secrets absent from 1,753,123 bytes of frontend static assets and 212,188 bytes of backend logs at check time; reset requires secret plus role; explicit CORS |
| Original regression preservation | All six saved original regression-file SHA-256 hashes unchanged; hardening tests also retained without edits |
| Public HTTPS deployment | **NOT VERIFIED / NOT DEPLOYED**; no checked Vercel/Render/Railway credentials available |

Artifacts: [schema inventory](deployment/schema.json), [restart persistence](deployment/persistence.json), [secret scan](deployment/security-check.json), [run 1](deployment/rehearsal-1.json), [run 2](deployment/rehearsal-2.json), [run 3](deployment/rehearsal-3.json), [fresh-volume run](deployment/clean-rehearsal.json). All three main runs ended CG001 98 READY, CG021 94 READY, CG030 98 READY after human override, CG048 95 INVESTIGATION and imported SYN-FHIR-101 98 READY.

The earlier PostgreSQL retry against a reused test database encountered the original interrupted-test fixture's fixed-ID collision. Verification now provisions a new UUID database each run; no fixture assertion was changed and the presentation database is never used for pytest. Browser verification must run from repository root for existing fixture paths.

## Compatibility defect found in real HTTP verification

FastAPI's default request-scoped yield cleanup commits after response sending. With real PostgreSQL I/O, a rapid generate-request followed by simulated-send could observe the old task before commit and return 409. The fix uses `Depends(session, scope="function")` on existing database dependencies so commit/rollback completes before success is sent. No business assertion or processing delay changes. A commit-failure regression requires HTTP 500 and redacted details rather than false success. See the [official dependency lifecycle](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/).

PostgreSQL row updates also exposed an implicit trace ordering assumption: unordered SELECT returned updated runs in physical row order. Passport traces now sort by persisted execution timestamp, with deterministic check/ID tie-breakers, so the same eight checks appear in execution order. A new regression inserts reversed execution times and verifies chronological output; the original browser assertion stays unchanged.
