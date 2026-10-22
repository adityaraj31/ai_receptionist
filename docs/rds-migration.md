# Move Postgres from Supabase/Neon to RDS `ap-south-1`

The current development database is a Supabase pooler in `ap-southeast-2`. Production
health data must stay in India. The ECS stack creates an RDS Postgres 16 instance in
`ap-south-1` with pgvector; this runbook moves existing data into it.

The Terraform stack already creates:

- private RDS Postgres 16 (`db.t4g.medium` by default), encrypted, no public access
- a generated password in Secrets Manager
- a `DATABASE_URL` secret consumed by the API and Arq worker
- pgvector via the Alembic migrations (`CREATE EXTENSION IF NOT EXISTS vector`)
- `btree_gist` for appointment/time-off exclusion constraints

## 1. Preflight

Record these before touching production:

```bash
# Source
psql "$SOURCE_DATABASE_URL" -c 'select version();'
psql "$SOURCE_DATABASE_URL" -c 'select extname, extversion from pg_extension;'
psql "$SOURCE_DATABASE_URL" -c 'select count(*) from appointments;'
psql "$SOURCE_DATABASE_URL" -c 'select count(*) from calls;'
psql "$SOURCE_DATABASE_URL" -c 'select count(*) from faq_chunks;'

# Target (RDS endpoint from terraform output; password from Secrets Manager)
psql "$TARGET_DATABASE_URL" -c 'select version();'
psql "$TARGET_DATABASE_URL" -c 'select 1;'
```

Confirm:

- Target `pgvector` and `btree_gist` are available. RDS Postgres 16 supports both; the
  migrations create the extensions. The master user can create extensions.
- `pg_dump`/`pg_restore` versions are at least the source server version.
- RDS has enough storage for the dump plus indexes. HNSW index rebuild can roughly double
  the FAQ table size temporarily.
- You have a maintenance window. The API can stay up for the dump, but stop writes before
  the final delta restore.
- A rollback path exists: keep the old database read-only for at least 7 days.

Never put connection strings in shell history on a shared machine. Use a password file,
`~/.pgpass`, or a temporary environment variable from your secret manager. Do not paste
them into tickets or chat.

## 2. Take a consistent dump

Run from a host with network access to Supabase/Neon and RDS. For Supabase, you may need
the IPv4 add-on or a direct connection rather than the transaction pooler; `pg_dump`
needs session-level features.

```bash
pg_dump \
  --format=custom \
  --no-owner \
  --no-acl \
  --file="/secure/ai-receptionist-$(date +%Y%m%d-%H%M).dump" \
  "$SOURCE_DATABASE_URL"
```

Keep the dump encrypted at rest, in India if possible (`/secure` on an `ap-south-1`
instance). Do not email it.

## 3. Restore into RDS

Restore into the empty RDS database. `--clean --if-exists` makes retries safe.

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
- a test booking against a free slot (then cancel it)
- `search_faq` from a staging API instance returns the same top answer

## 5. Final cutover

1. Put the clinic dashboard in maintenance mode or stop appointment writes.
2. Run a final dump/restore, or set up logical replication for a near-zero-downtime move.
3. Point the application at RDS:
   - Terraform-managed stack: update the `database_url` secret value to the RDS URL.
     Terraform owns this secret, so make the change in Terraform or import/update it
     deliberately. Do not leave a manually edited secret that the next apply overwrites.
   - Non-Terraform deploy: update `DATABASE_URL` in the secret/env and restart the API
     and Arq worker.
4. Run `alembic upgrade head` once against RDS.
5. Verify `/health`, login, appointment list, FAQ search, call detail, and one end-to-end
   booking.
6. Keep the old database unchanged and read-only for the rollback window.

The API normalises `postgresql://` to `postgresql+asyncpg://` and extracts
`sslmode=require`; RDS URLs from Terraform already use that form. `statement_cache_size=0`
is set for compatibility with poolers and remains safe on RDS, though it is not the
fastest setting for a direct connection.

## 6. Rollback

If validation fails after cutover:

1. Stop API and Arq writes.
2. Restore the old `DATABASE_URL` secret.
3. Restart the API and Arq worker.
4. Confirm `/health` and login.

Do not delete the RDS instance or old database until the rollback window closes and a
restore drill has passed. `deletion_protection = true` and a final snapshot are enabled
in Terraform.

## 7. Post-cutover checks

- Enable RDS automated backups and confirm the retention period (7 days in Terraform).
- Confirm encryption at rest and that the instance is not publicly accessible.
- Confirm CloudWatch logs export for Postgres is working.
- Add a weekly restore test to a scratch database.
- Update `DATABASE_URL` in developer `.env` files to the new staging endpoint; never put
  production credentials on laptops.
- Remove the Supabase/Neon project only after the retention/rollback window and a signed
  DPDP data-retention review.
