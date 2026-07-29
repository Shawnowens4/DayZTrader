# TODO_ROADMAP.md
# DXEMB — Prioritized Action Roadmap

---

1. **Create fresh repo with thin-root structure**
   - New private repo (`dxemb` or use DayZTrader PERM branch).
   - `docs/` folder with all four handoff files committed.

2. **Build minimal Docker skeleton — no business logic**
   - Bot: Gateway only, logs online, no cogs.
   - Flask: `/health` only, returns `{"status": "ok"}`.
   - DB: container connects, no schema yet.

3. **Verify skeleton boots clean on Windows 11 Docker Desktop**
   - `docker-compose up` zero errors.
   - `localhost:5000/health` returns 200 OK.
   - Bot confirms online, no crashes.
   - `docker-compose down -v` cleans up.

4. **Close Epic A0** (PHASE2_CHECKLIST.md A0.1–A0.6)

5. **Epic A — A1–A21 in dependency order**
   - Follow dependency chains from PHASE2_CHECKLIST.md exactly.

6. **Epic B — Automated tests**
   - B0 first (Docker test runner), then B1–B13.
   - All via `docker-compose run tests`.

7. **Epic C — Headless UI tests**
   - C0 (Playwright) + C7 (Discord harness) in parallel once A-deps met.
   - C1–C6 (dashboard) and C8–C11 (Discord) in order.

8. **Epic D — Audit pass**
   - D1–D5 require all A1–A21 complete.
   - D6 → `docs/AUDIT_REPORT.md`.

9. **Epic E — Real user testing + sign-off**
   - E0 → E1 → E2 → E3 → E4 → E5 → E6 (Phase 2 Sign-Off).

10. **🚩 FLAG: Auto-Trader pipeline needs its own Epic A–E breakdown**
    - Not started. Create `docs/AUTOTRADER_CHECKLIST.md`.
    - Required before Deployment Gate.

11. **🚩 FLAG: Casino/Tasks/Achievements needs its own Epic A–E breakdown**
    - Not started. Create `docs/CASINO_TASKS_CHECKLIST.md`.

12. **Only after Phase 2 E6 AND Auto-Trader sign-off: Deployment Gate toward Cloudflare**
    - Deployment Gate checklist:
      - Phase 2 E6 sign-off complete
      - Auto-Trader pipeline audit complete
      - `docker-compose up` clean boot confirmed
      - Discord OAuth2 local redirect confirmed
      - Nitrado confirmed outbound-poll only
      - Bot confirmed Gateway/WebSocket mode

---
*End of TODO_ROADMAP.md*
