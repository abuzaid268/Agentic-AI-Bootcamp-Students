# Trip Store persistence

My Trips lists the trips saved in the Rihla Trip Store (`services/travel_api.py`, reached by the backend through
the MCP `save_trip` tool and the REST reads). By default that store keeps everything in memory, so a restart
erases every saved trip. Set `TRAVEL_DB_PATH` and it keeps them in a SQLite file (`services/trip_db.py`).

## Setup

1. In the `.env` the **Trip Store** process reads, add a path (it is created on first use, with its folder):

   ```
   TRAVEL_DB_PATH=.rihla-data/trips.sqlite3
   ```

   `.rihla-data/` and `*.sqlite3` are git-ignored: the file holds real travellers' trips. Never commit it.
2. Restart the Trip Store (`uvicorn services.travel_api:app --port 8103`). Nothing else changes: the backend,
   the MCP tools and the frontend use the same API.

No migration is needed: existing in-memory trips cannot be recovered (they were never written anywhere), and a
new database starts empty. The schema has a version (`meta.schema_version`); a future change bumps it, and a
store refuses a database written by a newer version instead of misreading it.

## What is stored

| Table | Holds |
|---|---|
| `trips` | every saved trip record, exactly as the store serves it: the itinerary (with `rihla_save` for a trip saved with limitations or as an unverified draft: its status, verification result, limitations, costs and plan version), dates, totals, `traveller_id` (the owner), `created_at` |
| `idempotency` | each save's Idempotency-Key (the approval or acceptance id) and its answer: a retried save after a restart still creates no second trip |
| `meta` | the next trip number (ids are never reused) and the schema version |
| `travellers` | preferences saved through the API (traveller memory, activity pace) |

The seed data in `services/data` is not copied; it is loaded from its files as before. A status is never
changed by storing or loading: an unverified trip stays unverified.

## Safety

- Every write is one SQLite transaction, made before the store answers. If it fails, the request fails and
  nothing is reported as saved.
- Ownership is checked by the Rihla backend: `/api/trips` and `/api/trips/{id}` use the signed-in user's
  traveller id, never one the browser sends. The store itself needs its API key (`TRAVEL_API_KEY`).
- The store's `/admin/*` endpoints need no key (they exist for the eval runner's throwaway stores). With
  `TRAVEL_DB_PATH` set they answer 403, unless `TRAVEL_ADMIN_ENDPOINTS=on`. Never turn that on for real data:
  `/admin/reset` would erase the database.
- Leave `TRAVEL_DB_PATH` unset for the eval runner and the tests: they expect a fresh store each run.

## Backup

Stop the store, copy the `.sqlite3` file (and any `-wal` / `-shm` file next to it). To start over, stop the
store and delete them.

## Tests

`tests/test_trip_store_persistence.py`: restarts in-process and one real process restart (kill, start on the
same file, read back); statuses and details kept; per-traveller lists; no reused ids; idempotency across a
restart; a failed write saves nothing; admin endpoints off; in-memory behaviour unchanged without the setting.
