"""
bot/services/nitrado_monitor.py — Nitrado health monitor definitions.

Phase 1: State enum, event enum, status classification sets,
         and MonitorConfig dataclass only.
         Nothing is executable. No async. No tasks. No polling loop.
Phase 7: Full NitradoMonitor class implementation.

Import path: bot.services.nitrado_monitor
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class MonitorState(str, Enum):
    """All valid states for the Nitrado server health monitor."""
    IDLE        = "IDLE"         # Monitor disabled
    HEALTHY     = "HEALTHY"      # Server running normally
    DEGRADED    = "DEGRADED"     # Transitional (starting/stopping) — no fail count
    UNREACHABLE = "UNREACHABLE"  # Server offline/error — failure counter active
    RESTARTING  = "RESTARTING"   # Restart issued — duplicate lock active
    COOLDOWN    = "COOLDOWN"     # fast_retry_count exhausted — slow polling
    ESCALATED   = "ESCALATED"    # max_total_retries hit — restarts halted
    RECOVERED   = "RECOVERED"    # Transitional -> always resolves to HEALTHY after logging


class MonitorEvent(str, Enum):
    """Event types written to monitor_log.event_type."""
    CHECK_OK           = "CHECK_OK"
    CHECK_FAIL         = "CHECK_FAIL"
    CHECK_DEGRADED     = "CHECK_DEGRADED"
    RESTART_ATTEMPT    = "RESTART_ATTEMPT"
    MANUAL_RESTART     = "MANUAL_RESTART"
    BACKOFF_TRANSITION = "BACKOFF_TRANSITION"
    RECOVERY           = "RECOVERY"
    ESCALATED          = "ESCALATED"
    OVERRIDE_RESET     = "OVERRIDE_RESET"


# Nitrado API server status string classification
HEALTHY_STATUSES:     frozenset[str] = frozenset({"running", "active"})
DEGRADED_STATUSES:    frozenset[str] = frozenset({"starting", "stopping", "restarting", "suspended"})
UNREACHABLE_STATUSES: frozenset[str] = frozenset({"offline", "stopped", "error", "unknown"})


@dataclass
class MonitorConfig:
    """
    Runtime config for the Nitrado monitor.
    Phase 7: loaded from settings.yaml nitrado_monitor section.
    All defaults here match settings.yaml defaults.
    """
    enabled:                     bool = False
    check_interval_seconds:      int  = 60
    fast_retry_interval_seconds: int  = 180
    fast_retry_count:            int  = 10
    slow_retry_interval_seconds: int  = 1800
    max_total_retries:           int  = 50
    restart_enabled:             bool = False
    restart_window_seconds:      int  = 300
    log_channel:                 str  = "admin-logs"
    dm_admin_on_escalation:      bool = True
    notify_on_recovery:          bool = True


# TODO Phase 7: implement NitradoMonitor class with:
#   async def start()                  — begin tasks.loop polling
#   async def stop()                   — graceful shutdown
#   async def check_server_health()    — poll Nitrado API, return raw status string
#   async def handle_failure()         — increment count, transition state, maybe restart
#   async def handle_recovery()        — reset count, log RECOVERY, notify channel
#   async def issue_restart()          — POST to Nitrado restart endpoint
#   async def transition_to_cooldown() — switch polling interval, log BACKOFF_TRANSITION
#   async def escalate()               — log ESCALATED, DM admin, stop restarts
#   async def admin_override_reset()   — log OVERRIDE_RESET, return to HEALTHY cycle
#   def get_current_state() -> MonitorState — read singleton row from DB
