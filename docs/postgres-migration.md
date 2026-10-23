# Move Postgres to a managed instance

Use this runbook when moving from the local Compose database or a hosted pooler to a
managed Postgres instance in India. The target can be RDS, Cloud SQL, or any managed
Postgres service that supports `pgvector` and `btree_gist`.

The application needs:

- PostgreSQL 16
- the `vector` extension for FAQ embeddings
- the `btree_gist` extension for appointment and time-off exclusion constraints
- private networking and encryption at rest
- automated backups with a tested restore path

The Alembic migrations create the extensions, but the database user must be allowed to
create extensions.

## 1. Preflight

Record these before touching production:

```bash
# Source
psql "$SOURCE_DATABASE_URL" -c 'select version();'
psql "$SOURCE_DATABASE_URL" -c 'select extname, extversion from pg_extension;'
psql "$SOURCE_DATABASE_URL" -c 'select count(*) from appointments;'
psql "$SOURCE_DATABASE_URL" -c 'select count(*) from calls;'
psql "$SOURCE_DATABASE_URL" -c 'select count(*) from faq_chunks;'

# Target
psql "$TARGET_DATABASE_URL" -c 'select version();'
psql "$TARGET_DATABASE_URL" -c 'select 1;'
```

Confirm:

- `vector` and `btree_gist` are available on the target.
- `pg_dump` and `pg_restore` are at least the source server version.
- The target has enough storage for the dump plus indexes. Rebuilding the HNSW index can
  temporarily roughly double the FAQ table size.
- You have a maintenance window. Reads can continue during the dump, but stop writes
  before the final delta restore.
- A rollback path exists: keep the old database unchanged and read-only for at least
  7 days.

Do not put connection strings in shell history on a shared machine. Use `~/.pgpass`, a
password file, or a temporary environment variable from your secret manager.

## 2. Take a consistent dump

Run from a host that can reach both databases. For a pooler, use a direct/session
connection because `pg_dump` needs session-level features.

```bash
pg_dump \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="/secure/ai-receptionist-$(date +%Y%m%d-%H%M).dump" \
  "$SOURCE_DATABASE_URL"
```

Keep the dump encrypted at rest and in India. Do not email it.

## 3. Restore into the target

Restore into an empty database. `--clean --if-exists` makes retries safe.

```bash
pg_restore \
  --clean --if-exists \
  --no-owner --no-acl \
  --dbname="$TARGET_DATABASE_URL" \
  /secure/ai-receptionist-YYYYMMDD-HHMM.dump
```

Then run Alembic to create any migrations newer than the dump and to ensure extensions:

```bash
cd api
DATABASE_URL="$TARGET_DATABASE_URL" uv run alembic upgrade head
```

## 4. Validate before cutover

Run the same queries against source and target and compare:

```sql
select count(*) from clinics;
select count(*) from doctors;
select count(*) from availability_rules;
select count(*) from appointments;
select count(*) from calls;
select count(*) from transcripts;
select count(*) from faq_chunks;
select count(*) from callback_tasks;

-- Must return vector and btree_gist
select extname from pg_extension where extname in ('vector', 'btree_gist');

-- HNSW index must exist on faq_chunks.embedding
select indexname, indexdef
from pg_indexes
where tablename = 'faq_chunks';

-- Exclusion constraint must exist on appointments
select conname, contype
from pg_constraint
where conrelid = 'appointments'::regclass;
```

Also spot-check:

- one known appointment with its clinic, doctor, patient, and language
- one FAQ that previously matched a known query
- a test booking against a free slot, then cancel it
- `search_faq` from a staging API instance returns the same top answer

## 5. Final cutover

1. Put the clinic dashboard in maintenance mode or stop appointment writes.
2. Run a final dump/restore, or use logical replication for a near-zero-downtime move.
3. Point the application at the new database:
   - update `DATABASE_URL` in `.env` or the secret manager
   - restart the API, Arq worker, and any process that opens the database directly
4. Run `alembic upgrade head` once against the new database.
5. Verify `/health`, login, appointment list, FAQ search, call detail, and one end-to-end
   booking.
6. Keep the old database unchanged and read-only for the rollback window.

The API normalises `postgresql://` to `postgresql+asyncpg://` and extracts
`sslmode=require`. Most managed Postgres URLs use that form. `statement_cache_size=0` is
set for compatibility with poolers and remains safe on a direct connection, though it is
not the fastest setting there.

## 6. Rollback

If validation fails after cutover:

1. Stop API and Arq writes.
2. Restore the old `DATABASE_URL`.
3. Restart the API and Arq worker.
4. Confirm `/health` and login.

Do not delete the old database or the managed instance until the rollback window closes
and a restore drill has passed.

## 7. Post-cutover checks

- Enable automated backups and confirm the retention period.
- Confirm encryption at rest and that the database is not publicly accessible.
- Confirm database logs are retained and searchable.
- Add a weekly restore test to a scratch database.
- Update `DATABASE_URL` in developer `.env` files to the new staging endpoint; never put
  production credentials on laptops.
- Remove the old database only after the retention/rollback window and a DPDP
  data-retention review.
