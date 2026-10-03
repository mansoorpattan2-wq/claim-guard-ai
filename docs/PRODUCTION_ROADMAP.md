# Prototype versus production roadmap

The competition demo is feature-frozen. These are future validation gates, not delivered capabilities or promises.

| Area | Verified prototype | Production replacement / acceptance gate |
|---|---|---|
| Persistence | SQLite recovery and locally verified PostgreSQL/Docker schema v3, idempotent seed/reset and CG021 restart persistence | Public managed-PostgreSQL verification, backups/restore drills, future upgrades/rollback, indexes and measured load |
| Identity/access | Local demo-role sessions and server role/org checks | Real identity provider, explicit tenant provisioning, least privilege, session lifecycle, audit access and adversarial isolation tests |
| Evidence storage | Local opaque file keys | Encrypted governed object storage, access-bound signed retrieval, retention/deletion policy, malware scanning and safe parsing isolation |
| Extraction | UTF-8 TXT, text PDF, DOCX paragraphs; unreadable sources require review | Validated OCR/layout extraction, measured uncertainty, provenance linking and representative quality evaluation |
| Check orchestration | Eight local deterministic nodes and persisted job/trace | Durable workers/queue, transactional idempotency, concurrency controls, failure supervision; evaluate LangGraph or another runtime only against actual branching requirements |
| Policy knowledge | Synthetic source/date/org filtering and keyword ranking | Governed insurer-approved knowledge ingestion/versioning, validated retrieval, review/release controls; evaluate vector or LLM layers with bounded output and citation/failure tests |
| Clinical/billing rules | Demonstration rules and illustrative readiness | Expert-governed rule packs, payer/clinical review, outcome and calibration studies; human gates until validated |
| Investigation | SQL projection, fingerprint/template/frequency/history leads | Permitted reference datasets, graph/query scaling, statistical baselines, fairness/error analysis and investigator verification |
| FHIR/NHCX | Narrow synthetic local Bundle mapping; NHCX disconnected | Current applicable profile validation, authenticated transport, consent/access, sandbox trials, acknowledgment/error handling and required conformance review |
| Other integrations | HIS/HMIS, email and webhooks disconnected | Authenticated adapters, contract tests, rate limits, reliable delivery, replay/idempotency and credentials management |
| Operations | Local logs, test suite, presenter preflight | Metrics/tracing, incident runbooks, alerting, service-level measurements, dependency/security maintenance and recovery drills |

No production security, clinical validation, integration conformance, fraud accuracy, savings or scale claim should be made before its gate has evidence. Preserve CG021 and the current regression contract while adding future governed capabilities.
