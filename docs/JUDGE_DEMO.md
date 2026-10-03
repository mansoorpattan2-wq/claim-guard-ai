# Four-minute judge runbook

The click sequence below is unchanged for the locally verified PostgreSQL deployment at `http://127.0.0.1:3100/dashboard`. Use [DEPLOYMENT.md](DEPLOYMENT.md) for Docker startup, explicit bootstrap and preflight with ports 3100/8100. Production demo resets require the presenter secret or authenticated container administration; the public browser reset intentionally rejects requests without that secret. Local SQLite startup/reset commands below remain the recovery path. Public HTTPS delivery has not yet been verified.

Start → reset → preflight before judging:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
powershell -ExecutionPolicy Bypass -File .\reset-demo.ps1
powershell -ExecutionPolicy Bypass -File .\preflight-demo.ps1
```

Require **DEMO READY**. Open `http://127.0.0.1:3000/dashboard` as Claims Executive. Avoid the print dialog during timed narration.

| Time | Exact page/clicks and expected state | One-sentence narration | If the action fails |
|---|---|---|---|
| 0:00–0:20 | `/dashboard`: show 50 claims and READY / NEEDS_RESOLUTION / HUMAN_REVIEW / INVESTIGATION; use the four workflow shortcuts. | “ClaimGuard prepares evidence and resolves readiness gaps while humans retain decision authority.” | Use Retry; if the backend is down, start it and run preflight; identify a static screenshot walkthrough explicitly if recovery exceeds the session. |
| 0:20–0:40 | Click CG001 shortcut → 98%, Ready → Print / PDF → `/claims/CG001/passport`, inspect summary/print controls. | “A clean case travels with a professional, source-preserving evidence passport.” | Retry export or use the existing JSON Export passport; do not report a failed export as successful. |
| 0:40–1:55 | `/claims/CG021` → 63%, Needs resolution → View evidence → page 4/section 4.2 highlight → Back to CG021 passport → Resolve → Generate request → Simulate request → Simulate response → Validate & update passport → 94%, Ready; inspect the 63 → 94 strip, Agent Trace and Audit tabs. | “The source-backed missing-report requirement becomes a validated response and four targeted checks, with the entire resolution retained.” | Retry failed request using the same enabled action; refresh restores persisted task progress; invalid evidence leaves 63%; repeat completion is idempotent; preserve the truthful failed state. |
| 1:55–2:35 | `/knowledge` → applicable 2026-10-02 → Test retrieval for prefilled anaesthesia/LAP-APP-01 → inspect PKG-6.1 ranking/citation; `/review` → select Medical Reviewer → CG030 queue item → Override → show disabled Record disposition → enter “Synthetic demonstration review: package exception confirmed by reviewer.” → Record disposition → READY notice; CG030 now 98%. | “A governed source supports advice, and an identified human records the exception and its reason.” | Retry retrieval; empty/outdated evidence is human review, not an answer; failed override leaves the previous state—do not bypass the mandatory reason. |
| 2:35–3:15 | `/investigations` → focus CG048 → select Document Shared diagnostic source → inspect fingerprint/connections, invoice/frequency/12-day signals and CG045–CG050. | “These connected patterns are INVESTIGATION LEADS that require verification, never a fraud determination.” | Retry graph; if unavailable, open `/claims/CG048` for persisted findings and linked claims. |
| 3:15–3:45 | `/integrations` → Claims Executive → show Not Connected cards → Load synthetic FHIR Bundle → Import & analyse FHIR Bundle → Open imported Claim Passport → SYN-FHIR-101 / 98%, Ready. | “The narrow synthetic FHIR Demo Adapter maps a real local Bundle into the same analysis pipeline; NHCX is not connected.” | Correct malformed JSON or reload the bundled sample; a failed job offers Retry analysis; otherwise skip import and describe its disclosed scope. |
| 3:45–4:00 | Imported Passport → Agent Trace (eight checks) → Audit (FHIR bundle imported) → point to Print / PDF. | “Sources, findings and human decisions remain together for downstream human review.” | Stay on a persisted Passport; state exactly which live step failed. |

## Recovery and fallback

The demo needs local Next.js, FastAPI and SQLite only. Missing LLM keys, PostgreSQL, Docker, Neo4j, vector/OCR services or external integration accounts do not affect the four seeded stories because they are not used. Fonts and the sample Bundle are bundled locally.

If the local backend stops, run `start.ps1`, then reconnect the browser session and retry. Failed analysis after restart is explicitly FAILED and requires Retry analysis. If a process is listening but unhealthy, inspect the named error log and restart that service; the startup script does not kill unknown processes automatically. Correct stale presentation state with reset **after** outstanding jobs finish, then preflight. The reset button asks for confirmation; cancelling changes nothing.

Static screenshots in `docs/hardening/` are a disclosed walkthrough fallback only. They must never be described as a successful live integration or a newly processed claim.

Normal preflight performs no persisted mutation; it reads claim/database/knowledge/reset availability and creates only an ephemeral demo session token. Reset correctness is independently covered by regression tests. Use `reset-demo.ps1` explicitly to change presentation state.
