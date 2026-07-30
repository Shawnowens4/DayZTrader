# DXEMB - DayZ Xbox Escrow Marketplace Bot

## Phase 0 Skeleton (Docker-only, no business logic)

This is the minimal Docker skeleton: bot connects to Discord Gateway (or
runs in no-op mode without a token), Flask serves /health, Postgres boots
with a stub init file.

### Quick start (Windows 11, Docker Desktop, Linux containers mode)

1. Copy .env.example to .env and fill in DISCORD_BOT_TOKEN if you want
   the bot to actually connect (optional for this skeleton phase).
2. Run:
   docker compose up --build
3. Verify:
   - Web: http://localhost:5000/health should return {"status": "ok"}
   - Bot: logs should show either "DXEMB bot online as ..." or the no-op
     mode message.
   - DB: should report healthy in docker compose ps.
4. Tear down:
   docker compose down -v

See docs/PHASE2_CHECKLIST.md for the full build roadmap.
