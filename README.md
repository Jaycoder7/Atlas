# Atlas

Atlas is an engineering-program intelligence layer for complex hardware development. It connects schedules, requirements, validation results, hardware prototypes, risks, and engineering changes in one explainable program graph.

## Quick start

1. Copy `.env.example` to `.env`. The default `ATLAS_AUTH_MODE=demo` is intentionally local-only and signs in as a demo administrator.
2. Run `docker compose up --build`.
3. Open [http://localhost:3000](http://localhost:3000). API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).
4. Trigger the primary scenario with `python3 tools/test-runner/simulate.py thermal-failure`.

To enable advisory impact suggestions, run `docker compose --profile ai up`, then pull the configured model once with `docker compose exec ollama ollama pull qwen2.5:7b-instruct`.

## Auth0 production mode

Set `ATLAS_AUTH_MODE=auth0` and fill in the Auth0 variables in `.env`. Configure an Auth0 API using the configured audience, enable Organizations, add `org_id` and an `https://atlas.local/roles` array to access tokens, and grant machine clients the `test-results:write` permission. Human tokens are tenant-scoped by `org_id`; machine clients are mapped to an organization in Atlas.

Callback: `http://localhost:3000/auth/callback`. Logout URL: `http://localhost:3000`. Web origin: `http://localhost:3000`.

## Commands

- `make api-test` — backend unit/integration tests.
- `make web-test` — frontend tests.
- `make seed` — idempotently recreate/refresh the avionics demo data.
- `make demo` — submit the Rev C thermal failure.
- `make generate-api` — regenerate TypeScript types from the running FastAPI OpenAPI document.

The fixed demo includes six teams, 50 tasks, 30 requirements, 40 validation tests, four prototypes, ten risks, and five engineering changes. AWS deployment, firmware, holiday calendars, per-program permissions, and third-party imports are intentionally outside v1.
