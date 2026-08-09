# DXEMB - DayZ Xbox Escrow Marketplace Bot

## Current Local Baseline

DXEMB currently supports a local Docker-based web baseline with PostgreSQL and
the Flask admin surface. The least invasive supported Phase 1 startup path is
to run the database and web services only.

### Required environment variables

Copy `.env.example` to `.env`.

Required for the local web baseline:
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DATABASE_URL`

Optional for the Phase 1 web-only run:
- `DISCORD_BOT_TOKEN`
- `DISCORD_REDIRECT_URI`

### Supported local startup (Phase 1)

Windows 11, Docker Desktop, Linux containers mode:

1. Copy `.env.example` to `.env`.
2. Start the local web baseline:
   `docker compose up -d db web`
3. Verify service state:
   `docker compose ps`
4. Open the primary pages:
   - `http://localhost:5000/`
   - `http://localhost:5000/catalog`
   - `http://localhost:5000/vehicles`
   - `http://localhost:5000/health`
5. Stop the local stack when finished:
   `docker compose down`

### Verified Phase 1 route results

Latest verified local web baseline:
- `/` -> HTTP 200
- `/catalog` -> HTTP 200
- `/vehicles` -> HTTP 200

Relevant local validation commands:
- `python -m unittest tests.test_web_visual_foundation_slice_a tests.test_catalog_thumbnail_workflow_slice_b`
- `git diff --check`

### Notes

- This Phase 1 baseline does not change vehicle compatibility approvals.
- Blocked/review-required compatibility records remain blocked.
- The bot service is not required to verify the primary Phase 1 web pages.

See `docs/TODO_ROADMAP.md` for the current local-release roadmap.
