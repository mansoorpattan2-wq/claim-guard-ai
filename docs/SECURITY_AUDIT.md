# Practical competition security audit

Subsequent deployment hardening adds explicit production CORS, credential-free liveness/readiness, commit-before-success, redacted structured server events and a server-only presenter reset secret. See [deployment secret scan](deployment/security-check.json), [deployment tests](../backend/tests/test_deployment.py) and [DEPLOYMENT.md](DEPLOYMENT.md). Public role selection remains prototype identity; the reset key protects reset only. No public HTTPS security or penetration-test claim is made.

Scope: local synthetic-data hackathon application, not a penetration test or production certification.

| Check | Evidence / finding |
|---|---|
| Secrets and environment | `.env`, database, vendor/dependency folders, logs and upload storage are ignored. No live API credentials are required. `local_demo` in optional compose configuration is an explicit local example password, not a production secret. Source and browser-bundle heuristic scanning is recorded with the final checks; it cannot prove absence of all possible secrets. |
| Frontend/server separation | Frontend uses a server-side API proxy and ephemeral browser session token. No server model key is configured or injected as NEXT_PUBLIC data. |
| Server authorization | API reads/writes enforce actor token, role and organization; regression tests cover missing token, Auditor write denial and cross-org isolation. Demo role selection is intentionally open on loopback; it is not production authentication. |
| Upload paths/types | User filename is reduced to basename; original bytes are stored under generated opaque IDs. Extensions, signatures, UTF-8, per-file size, document count and PDF/DOCX parsing limits are constrained. Filename text is escaped by React. |
| API validation | Pydantic constrains inputs; dates, chronology, identity, signature-field presence, FHIR references/base64/currency/totals are checked. Failure does not increase readiness to PASS/READY. Concurrent/repeated completion is idempotent. |
| HTML/injection | Printable user content uses HTML escaping; the preview iframe does not permit scripts. Source text is rendered as text. SQLAlchemy queries avoid string-built SQL. FHIR remote references are rejected rather than fetched. |
| User-visible errors | FastAPI debug mode is off. The API client converts backend 5xx/network failures to a recovery message and hides server error bodies. Validation messages remain actionable. No exception stack trace is deliberately rendered. |
| CORS/network binding | Backend CORS lists the two local frontend origins; no wildcard. Backend/frontend start on loopback; optional PostgreSQL publishes only on loopback. |
| Synthetic marking | Demo Mode indicator, footer, policy sources, response samples, FHIR adapter and printable report explicitly mark synthetic/prototype/demo scope. Seed identities are fictional aliases; there is no imported real dataset. |
| Dependency advisory check | `npm audit` reported zero advisories for the installed frontend lockfile during hardening. This is a point-in-time registry report, not proof of security. Python dependencies were not comprehensively vulnerability-audited. |

There is no Git repository in this workspace, so a commit-history secrets audit cannot be claimed. The audit checks present source/configuration and the generated browser assets.

Production work remains: real identity/session lifecycle, consent and lawful data access, encryption at rest/in transit, secret management, malware/safe-parser isolation, rate/body limits, CSRF/threat-model review, retention/deletion, protected historical access, production tenant isolation, vulnerability maintenance, backups and penetration testing. Do not use real patient data in this local demo.
