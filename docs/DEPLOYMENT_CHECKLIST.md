# Deployment acceptance checklist

## Local container verification

- [x] SQLAlchemy retained; claim rules, weights and scenario definitions unchanged.
- [x] PostgreSQL migrations v1-v3 run on a fresh database and repeated safely.
- [x] Deliberate revision failure rolls back DDL and version records together.
- [x] All 15 tables checked against metadata: column types/nullability, primary keys, foreign keys, defaults and index inventory (`deployment/schema.json`).
- [x] Existing seed run twice without duplicating the initial 50 claims; knowledge, graph and review checked in tests.
- [x] CG021 63 -> 94 -> backend stopped/restarted -> 94 with equal task/trace/audit and human metadata -> reset twice -> 63 and 50 active claims (`deployment/persistence.json`).
- [x] Original runtime upload bytes survive backend restart on the named upload volume.
- [x] Health/readiness contain no credentials; readiness failure is 503; no false success after commit failure.
- [x] Deployment reset requires a secret plus an allowed role; unauthorized reset rejected.
- [x] Explicit CORS; no wildcard; no database credentials in frontend build inputs.
- [x] Production startup never seeds, migrates or resets; bootstrap commands separate.
- [x] SQLite recovery suite: 40 passing, including all original 33.
- [x] PostgreSQL portable suite: 39 passing; one unchanged SQLite-specific test runs in SQLite.
- [x] Production Docker frontend build, strict TypeScript, ESLint, Prettier and baseline Ruff lint/format checks.
- [x] Final PostgreSQL production browser suite: 19 passing; three consecutive complete reset rehearsals pass.
- [x] SQLite recovery browser suite: 19 passing on final code; local reset/preflight DEMO READY.
- [x] Fresh-volume Compose preflight DEMO READY and complete judge flow pass, recorded in POSTGRES_MIGRATION.md.

## Public deployment gates (not completed)

- [ ] Provider account/repository connected; managed PostgreSQL provisioned with provider TLS/network settings.
- [ ] Backend deployed as one process / one replica; actual frontend domain in ALLOWED_ORIGINS.
- [ ] Original upload retention provided by persistent disk, or ephemeral-byte limitation accepted explicitly.
- [ ] API_URL set to the actual HTTPS backend before the frontend build.
- [ ] Migrate and seed executed explicitly; no startup/reset automation.
- [ ] Both public HTTPS URLs actually respond; health/readiness verified against that deployment.
- [ ] Authorized public reset -> read-only public preflight -> 50 claims and exact initial four stories.
- [ ] Complete public judge sequence three consecutive times, including CG021 after refresh, evidence, audit/trace, human reason, retrieval, graph, FHIR and final reset.
- [ ] Managed database restart/redeploy persistence and backup/restore procedures checked.

Do not label public deployment complete until these public gates pass. Exact configuration, commands, storage/auth limits and rollback are in [DEPLOYMENT.md](DEPLOYMENT.md).
