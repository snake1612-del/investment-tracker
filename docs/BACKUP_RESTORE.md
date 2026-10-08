# Backup & Restore v0.1

Operator-only; no public endpoint or automatic job. Use Python 3.14/API dependencies
and PostgreSQL client tools on PATH. Use the same PostgreSQL major as the source
(currently 18); restoration to an older server is rejected. Run from `apps/api`.
Windows additionally requires PowerShell 7 (`pwsh`) and native `icacls` for private
artifact ACLs; POSIX uses owner-only 0700 directories / 0600 files.
Artifacts must be outside the checkout or inside its already deployment-excluded
`tmp`/`temp` directory. The backup tool enforces this; no Vercel configuration changes
are needed. Never copy backups into deployment sources.

Supply `BACKUP_DATABASE_URL` or `RESTORE_DATABASE_URL` securely in the operator
process, using a native PostgreSQL URI/conninfo (not the SQLAlchemy driver prefix).
Require a single direct/unpooled endpoint and TLS for remote databases. Never paste
credentials into CLI arguments, logs, Git, PRs, or chat. Preserve stricter TLS and
channel-binding options. Verify the endpoint/project and environment before acting.

Local operations enforce loopback. For cloud operations independently verify and
set distinct `STAGING_DATABASE_HOST` and `PRODUCTION_DATABASE_HOST` to the direct
hostnames; the URL must match its declared environment. Production recovery also
requires `PRODUCTION_RECOVERY_HOST` for the designated empty destination (never the
Staging hostname). These operator identity bindings contain no credentials and are
not exported in the artifact. Incorrect bindings must not be used to bypass safety.

## Commands

```bash
uv run python -m operator_tools.backup backup --environment local --output ../../tmp/backups
uv run python -m operator_tools.backup validate ../../tmp/backups/<artifact>.tar
uv run python -m operator_tools.backup restore ../../tmp/backups/<artifact>.tar --environment local
```

The bundle contains exactly `database.dump` (pg_dump custom format), `manifest.json`
and `SHA256SUMS`. Manifest v1 records UTC creation, environment, Alembic revision,
PostgreSQL/pg_dump versions, Git SHA and snapshot row counts. No derived state,
roles/global configuration or credentials are exported. Restore ignores source
ownership and ACLs. Tar member ownership labels are stripped.

Backup uses one exported consistent snapshot for data, revision and counts.
Application writes may continue. **Exclude concurrent migrations and automatic
migration startup for the entire backup**; version/table locks are additional
protection, not a replacement for operator coordination. Use a dedicated private
output directory: the tool restricts it to the current owner (POSIX mode or Windows
ACL). Files are assembled privately and published only after structural validation.
An interrupted `.incomplete-*` directory is never a valid restore input; investigate
and remove it explicitly after ensuring no backup process is still using it.

Validation checks envelope, metadata, checksums, readable archive, expected tables
and captured Alembic state. **Artifact-valid does not mean recovery-ready.**
Checksums detect corruption, not malicious alteration/authenticity. Restore only
trusted operator-created archives: PostgreSQL archives contain executable SQL.

## Restore policy

The destination must be an empty, dedicated recovery database. Stop all target
writes/DDL and keep exclusive operator control through restore/verification.
Existing user objects cause refusal; no drop, truncate, merge or overwrite occurs.
pg_restore uses fail-fast and a single transaction; PostgreSQL errors roll back.
The tool then checks captured revision and row counts. This is not yet complete
application recovery verification.

- Current revision `0003_csv_imports`: restore captured schema directly, including
  immutable `csv_imports` receipts (Decision 023).
- Known ancestors `0001_initial_persistence` / `0002_market_prices`: restore captured schema first, then
  run the normal approved explicit Alembic upgrade to head, current and check.
- Unknown/newer/non-lineage revision: reject before changing the target.

Do not point an upgrade at the source. Set the restored target's operator migration
configuration according to OPERATIONS.md. No migrations run inside these tools.
After restore/forward upgrade, verify tables, constraints/FKs/indexes, exact rows
(IDs, NUMERIC, dates, timestamps, relations, prices), identity next inserts and
application health/read/reconstructed financial results before resuming traffic.

## Production safety

Local artifacts restore only to Local recovery; Staging artifacts to empty Staging
or isolated Local recovery. Production artifacts restore only to explicitly named
Production recovery. Production/non-production crossover is always refused.
Environment declarations are operator assertions, not provider discovery: verify
the actual endpoint and obtain independent disaster-recovery approval.

Production backup requires `--encrypted-storage`, acknowledging approved
encrypted-at-rest storage. The tool does not encrypt or verify disk encryption.
Use a protected encrypted filesystem/volume/container; encrypt before transferring
outside that boundary. Never use shared Staging/Preview/tests for real-data recovery.
Production restore additionally requires `--production-recovery --writes-stopped`.
If original Production is readable, take a fresh backup before any separate,
explicit destructive preparation. The restore command never prepares it for you.

All artifacts and extracted payloads are sensitive. Validation/restore temporary
directories are owner-only and colocated with the artifact (keep them within the
approved encrypted storage boundary for Production). Clear process credentials
after use. Git/deployment exclusions are defense-in-depth, not secure storage.

## Isolated drill

`tests/integration/db/test_backup_restore.py` seeds synthetic representative state
in the disposable test database, captures facts, backs up, restores into a separate
empty local database, compares exact persisted facts/schema/identity state, exercises
identity inserts and API reads/financial reconstruction, and tests forward upgrade.
It also covers invalid artifacts, unsafe environment routing, occupied targets and
actual restore rollback. It never connects to cloud databases or uses real data.
