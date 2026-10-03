> Earlier competition-hardening baseline. Subsequent deployment verification is in [POSTGRES_MIGRATION.md](POSTGRES_MIGRATION.md): PostgreSQL is now locally verified and the original tests remain preserved.

# Final measured verification

Verified locally on Windows, Python 3.14.3, Node.js 24.13.1, Next.js 16.3.8 and Chromium.

| Check | Result |
|---|---|
| Backend suite | **33 passed**: 28 preserved + 5 hardening |
| Browser suite | **19 passed (2.0 minutes)**: 10 preserved + 6 failure/reset tests + 3 complete rehearsals |
| Strict TypeScript / production build | Passed |
| ESLint / Prettier / Ruff lint and format | Passed |
| Existing regression files | All six unchanged by SHA-256 |
| Database | **SQLite verified**; migrations v1-v3, repeated seed/reset, isolated clean-database real startup |
| Frontend advisories | npm audit: zero advisories at check time |
| Presenter preflight | **DEMO READY** after final reset; no persistent mutation |

## Three consecutive reset rehearsals

The complete click sequence passed three consecutive times from a full reset on the final code. Every run ended CG001 READY/98%, CG021 READY/94%, CG030 READY/98% after human override, CG048 INVESTIGATION/95%, and imported SYN-FHIR-101 READY/98%. Each run starts CG021 at 63%. The automated browser runs omit spoken narration and presentation pauses; this is not a timed human speech rehearsal.

Raw reports: [run 1](hardening/rehearsal-1.json), [run 2](hardening/rehearsal-2.json), [run 3](hardening/rehearsal-3.json).

## Demo-critical timings

| Operation | Minimum-maximum across three local runs |
|---|---|
| Dashboard initial browser load | 715-1311 ms |
| Claim load | 359-780 ms |
| CG021 simulated request action | 439-502 ms |
| CG021 validation + targeted rerun round trip | 484-589 ms |
| Targeted deterministic computation (backend) | 7.79-8.32 ms |
| Knowledge query | 512-543 ms |
| Investigation graph load | 877-1367 ms |
| Synthetic FHIR import | 1041-1092 ms |
| Automated complete sequence (no narration) | 11381-13846 ms |

These are local browser/service timings on this machine with installed dependencies and a warmed development server, not real-world performance, cold infrastructure startup, model inference or production accuracy. There is no artificial processing delay. Job polling occurs every 350 ms as UI refresh behavior. Backend targeted computation is separately measured with a monotonic timer.

## Audit, recovery and security

Final route capture covers the 13 implemented views and 390/768/1024/1440 widths. See [route audit](hardening/route-audit.json), [hardening report](FINAL_HARDENING.md) and [security audit](SECURITY_AUDIT.md). Fault tests include unavailable API, 503 actions, malformed/unsupported files, job failure/retry/manual review, retrieval failure/empty results, invalid/duplicate resolution, refresh/back/double-click, stale readiness after reset/read failure, malformed FHIR and unavailable graph.

Backend tests use an isolated temporary database; browser tests exercise the running synthetic database. Final startup, two full resets and preflight were exercised. The full reset archives prior presentation history and imported claims and restores active decisions/tasks/readiness.

## Inspect screenshots/pages

- [Initial Passport](claim-passport-desktop.png) and [resolved CG021 transition](hardening/cg021-resolved.png)
- [Evidence Viewer](evidence-viewer-desktop.png)
- [Intake](intake-analysis-desktop.png), [human review](review-workspace-desktop.png), [knowledge](knowledge-desktop.png)
- [Printable Passport](printable-passport-desktop.png)
- [Graph](investigation-graph-desktop.png), [FHIR](fhir-integrations-desktop.png), [mobile graph](investigation-mobile.png)
- Final all-route screenshots: `docs/hardening/`

The printable screenshot shows the scrollable preview; standalone HTML includes the full report. SQLite is the only verified database. PostgreSQL, production identity, cloud integrations, live models/OCR/vector/graph services and server PDF remain outside verified scope. Dependency deprecation/environment-color warnings are non-failing. See [LIMITATIONS.md](LIMITATIONS.md).
