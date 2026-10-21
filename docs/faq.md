# FAQ retrieval

The voice agent answers clinic questions from a per-clinic FAQ list. Retrieval is
clinic-scoped, runs locally, and is designed to stay under 300 ms end to end.

## How it works

```
Caller question -> search_faq tool -> POST /api/v1/agent/faq/search (service key)
  -> fastembed (local ONNX, multilingual MiniLM, ~5 ms) -> pgvector cosine search
  -> closest active FAQ -> first 1-2 sentences -> agent replies
```

- Each FAQ is stored in `faq_chunks` as two kinds of rows: the question itself and one
  row per sentence-aligned answer chunk. Searching both lets a terse query like
  `address` match the question and a detail like `UPI` match the answer.
- Embeddings are 384-dimensional vectors from
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, generated on the API
  host. No caller text or FAQ text is sent to an external embeddings API.
- The HNSW cosine index (`ix_faq_chunks_embedding`) keeps the database lookup to a few
  milliseconds.
- A result is accepted when cosine similarity is high enough, or when it is moderately
  similar and the query shares a keyword with the FAQ. This stops "do you have a
  pharmacy?" from returning the parking answer.
- `search_faq` returns `found=false` when nothing is close enough. The agent then offers
  a clinic callback instead of inventing an answer.

### Latency

The eval measures HTTP + embedding + pgvector, with the API and Postgres on the same
machine:

```
cases: 14  recall@1: 1.00  p50: 12.7 ms  p95: 16.1 ms
```

In production the database round trip dominates. Keep the API and Postgres in the same
region (Mumbai for Indian clinics); a cross-region database can add 200-300 ms by
itself. The local embedding call avoids adding an LLM-provider round trip.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Local ONNX model. |
| `EMBEDDING_DIMENSIONS` | `384` | Must match the model and the `vector(384)` column. |
| `FASTEMBED_CACHE_PATH` | empty (`/tmp/fastembed_cache`) | Where the ~220 MB model is cached. |
| `EMBEDDING_WARMUP` | `true` | Load the model in the background at API startup. |
| `FAQ_MAX_DISTANCE` | `0.55` | Maximum cosine distance; higher means stricter. |
| `FAQ_HIGH_CONFIDENCE_SIMILARITY` | `0.55` | Below this, a keyword overlap is required. |
| `FAQ_ANSWER_MAX_CHARS` | `320` | Hard cap on the spoken answer. |

The first API start downloads the model. To avoid that on a cold deploy, pre-download it
during the image build and point `FASTEMBED_CACHE_PATH` at the baked-in directory.

## Ingest a corpus

The seed corpus lives in [../evals/faq_corpus.json](../evals/faq_corpus.json). Resolve the
clinic id from the dashboard URL or the `clinics` table, then run:

```bash
cd api
uv run python -m scripts.ingest_faqs --clinic-id <uuid>
uv run python -m scripts.ingest_faqs --clinic-id <uuid> --replace
uv run python -m scripts.ingest_faqs --clinic-name "Demo Family Clinic" --dry-run
```

`--replace` deletes the clinic's existing FAQ chunks first. Without it, each question in
the file is upserted and other questions are left alone. The script uses the configured
`DATABASE_URL`.

## Staff UI

Open **FAQs** in the dashboard to:

- add and edit a question/answer, and toggle it active or inactive;
- deactivate an answer without losing it (the agent stops using it immediately);
- upload a JSON or CSV file. JSON accepts a list or `{"faqs": [...]}`; CSV needs
  `question,answer` columns. Existing questions are reported as skipped.

Every write re-embeds the FAQ synchronously, so a change is searchable immediately. The
API is still clinic-scoped by the staff JWT.

## Agent integration

- `agent/api_client.py`: `search_faq(query)` calls
  `POST /api/v1/agent/faq/search` with `X-Service-Key`.
- `agent/agent_tools.py`: the `search_faq` function tool never raises into the call. A
  failure returns `ok=false` with a short fallback line; a miss returns `found=false`
  with a callback offer.
- `agent/prompts.py`: instructs the model to use only the returned answer, keep it to
  1-2 sentences, and never invent clinic facts.

## Eval

```bash
# ingest first, then run against a running API
cd api
uv run python -m scripts.ingest_faqs --clinic-id <uuid> --replace
uv run python ../evals/run_faq_eval.py --base-url http://127.0.0.1:8000
```

The runner warms the model, reports recall@1 and p50/p95 latency, and exits non-zero if
recall falls below 0.8 or p95 exceeds 300 ms. It reads `AGENT_API_KEY` or
`DEMO_AGENT_KEY` from `.env`. The cases are in
[../evals/faq_eval.json](../evals/faq_eval.json) and include Hindi queries.
