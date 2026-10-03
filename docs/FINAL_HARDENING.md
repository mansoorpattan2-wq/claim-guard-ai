> Historical phase record. PostgreSQL/Docker was subsequently verified locally; see [POSTGRES_MIGRATION.md](POSTGRES_MIGRATION.md) and [DEPLOYMENT.md](DEPLOYMENT.md). Public deployment remains unverified.

# Final competition hardening

Feature development is frozen. This pass changes reliability, disclosure, presentation and developer verification only; no product module was added.

## Audit and fixes

- Audited dashboard, claims, intake, Passport, Evidence Viewer, resolution, human review, trace, knowledge, investigations, integrations, audit and printable Passport. Browser audit covers 390/768/1024/1440 pixels; the final JSON and captures are in `hardening/`.
- Kept the existing visual identity. Moved four scenario shortcuts above the dashboard table, retained all four state metrics on small screens, and removed duplicate shortcut cards.
- Added a professional CG021 63 → 94/READY result strip with an audit link. No celebration animation or artificial processing delay.
- Removed the unsupported “all systems operational” claim; clarified deterministic execution and source wording. Integration cards remain explicitly Demo Adapter / Not Connected.
- Added native reset confirmation. Full reset clears active human decisions/tasks and archives previous-session audit/trace/decision records and imported claims. Baseline trace IDs are reused; repeated reset does not duplicate baseline runs. Historical audit is retained using `include_history=true`.
- Added action guards, bounded API recovery messages, resumed intake/job state after refresh, and explicit retry controls. Failed retrieval clears the previous grounded result. A failed workspace read hides cached readiness rather than presenting a stale READY state. Navigation reads are guarded against stale completion.
- Added actual deterministic targeted-rerun computation timing; preserved the CG021 validation, four targeted checks and 63 → 94 READY behavior.
- Startup checks readiness and refuses a conflicting unhealthy occupied port with its PID instead of starting another misleading process. It does not stop unknown processes. Presenter preflight is read-only with respect to persistent data.

## Failure coverage

| Failure | Verified behavior |
|---|---|
| Backend/network unavailable or API 503 | Actionable error and Retry; no successful result assumed |
| Malformed PDF / unsupported file / traversal-style filename | Signature/type rejection or sanitized basename and opaque storage key |
| Failed analysis / interrupted process | FAILED job/run, human-review state, retry; persisted job recovery |
| Retrieval failure or no applicable evidence | Previous grounded answer removed; retry or insufficient-evidence/human-review answer |
| Resolution request failure / invalid evidence | Remains 63%; corrective action remains available |
| Repeated completion / double click | One attachment and one targeted completion; readiness remains correct |
| Refresh/back navigation | Persisted resolution/intake state restores; source/back navigation works |
| Reset succeeds but following read fails | Cached READY Passport is hidden; Retry restores the verified 63% case |
| Malformed FHIR or invalid references/totals | No imported READY result from the failed import; correction/reload sample available |
| Graph unavailable | Error and Retry graph; linked CG048 Passport is the disclosed fallback |

Backend failure tests and browser route fault injection are distinguished: browser unavailable/503 cases are injected network responses, not a claim of resilience against every infrastructure failure.

## Database, security and fallback

Verified competition database: **SQLite**. Fresh isolated database verification exercises migrations v1–v3, repeated seed and real FastAPI startup on port 8001. Installed dependencies are reused. PostgreSQL/Docker remain untested production targets.

All six previously existing backend/browser regression files match their pre-hardening SHA-256 values (`hardening/regression-hashes.json`). No Git repository exists here, so no commit-history audit is claimed.

Present-source and generated browser-asset secret-pattern scanning and the frontend advisory check are recorded in [SECURITY_AUDIT.md](SECURITY_AUDIT.md). They are limited practical checks, not security certification. Production work is separate in [PRODUCTION_ROADMAP.md](PRODUCTION_ROADMAP.md).

The four seeded scenarios need no model key, vector service, OCR, graph server, PostgreSQL, cloud storage or external integration. A local backend outage still requires recovery; static captures may be used only as a clearly identified walkthrough. See [JUDGE_DEMO.md](JUDGE_DEMO.md) for exact clicks, narration and failure fallbacks.

Final counts, measured local timing ranges and three consecutive reset-run results are in [VERIFICATION.md](VERIFICATION.md). Full limitations are in [LIMITATIONS.md](LIMITATIONS.md), and judge-readable architecture/answers are in [TECHNICAL_DEFENSE.md](TECHNICAL_DEFENSE.md).
