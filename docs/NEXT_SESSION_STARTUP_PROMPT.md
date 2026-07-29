# NEXT_SESSION_STARTUP_PROMPT.md
# DXEMB — Next Session Startup Prompt

> Paste this entire block into a new AI session to resume the DXEMB project.

---

You are resuming work on the DXEMB project. Load the following context before doing anything else.

**Project identity:**
- Full name: D.X.E.M.B (DayZ Xbox/PlayStation Escrow Marketplace Bot)
- Package: `dxemb`
- Stack: Python, discord.py, Flask, PostgreSQL, Docker Compose (Windows 11 Docker Desktop)
- Currency: TZ-Credits
- GitHub: github.com/Shawnowens4/DayZTrader, branch PERM contains all handoff docs in docs/

**Load these from branch PERM docs/ folder:**
- MASTER_HANDOFF.md — project identity, locked rules, all subsystems
- PHASE2_CHECKLIST.md — Epic A–E Docker-gated checklist
- CURRENT_PROGRESS_SNAPSHOT.md — honest progress bars
- TODO_ROADMAP.md — prioritized action list

**Progress tracker rule (enforce from first response):**
Every response begins with labeled progress bars per phase/subsystem plus one Total Project Progress bar, using the 7-stage lifecycle. Coded-but-untested never exceeds 40–50%.

---

## STEP 1 — Fresh Repo Creation (walk me through as first-time-solo onboarding)

Walk through these steps one at a time, confirming each before proceeding:

1. Create a new private GitHub repo named `dxemb` (or confirm using DayZTrader/PERM).
2. Clone the repo locally.
3. Open in VS Code.
4. Confirm Docker Desktop installed and running on Windows 11.
5. Create thin-root structure:
   ```
   dxemb/
   ├── bot/
   │   └── main.py        # Gateway only, logs online, no cogs
   ├── web/
   │   └── app.py         # /health only, returns {status: ok}
   ├── db/
   │   └── init.sql       # Empty placeholder
   ├── docs/              # Four handoff files
   ├── .env.example
   ├── .gitignore
   ├── docker-compose.yml
   ├── Dockerfile.bot
   ├── Dockerfile.web
   ├── requirements.txt
   └── README.md
   ```
6. Run `docker-compose up` — all three containers start cleanly.
7. Confirm `localhost:5000/health` returns 200 OK.
8. Confirm bot logs online to console.
9. Run `docker-compose down -v` — clean teardown.

**ONLY goal of Step 1: skeleton boots. No logic. No models. No commands.**

---

## STEP 2 — Close Epic A0

Once skeleton runs cleanly:
- Verify and check off A0.1 through A0.6 from PHASE2_CHECKLIST.md.
- Update CURRENT_PROGRESS_SNAPSHOT.md Phase 0 bar to reflect real verified state.
- Commit updated docs to branch PERM.

---

## Rules to enforce throughout:
- No Cloudflare, no public URLs until Phase 2 E6 + Auto-Trader sign-off.
- Auto-Trader needs its own Epic A–E checklist — flag as open.
- Casino/Tasks/Achievements needs its own Epic A–E checklist — flag as open.
- All delivery is physical in-game spawn only. No claim codes.
- Auto-Trader and Player Marketplace terminology strictly separated.
- Console constraints: no liquid values, cargo = quantity/chance/damage only.

---
*End of NEXT_SESSION_STARTUP_PROMPT.md*
