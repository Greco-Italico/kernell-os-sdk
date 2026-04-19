"""
Kernell OS SDK — Shared Constants & Utilities
══════════════════════════════════════════════
Single source of truth for permission names, command blacklists,
and other values used across multiple modules.

This avoids the DRY violation of duplicating VALID_PERMISSIONS
in agent.py, gui.py, and dashboard.py.
"""
import time
import logging
from typing import Dict, List

logger = logging.getLogger("kernell.shared")


# ── Permission Names ─────────────────────────────────────────────────────────
# Whitelist of valid permission attribute names on AgentPermissions.
# Used by agent.toggle_permission(), GUI, and dashboard for validation.
VALID_PERMISSIONS = frozenset({
    "network_access",
    "file_system_read",
    "file_system_write",
    "execute_commands",
    "browser_control",
    "gui_automation",
})


# ── Command Safety ───────────────────────────────────────────────────────────
# Commands that are NEVER allowed, regardless of permission state.
# Checked by Agent._is_command_safe() before any shell execution.
COMMAND_BLACKLIST = frozenset({
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "chmod -R 777 /",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "cat /etc/shadow",
    "passwd",
    "userdel",
    "useradd",
})


# ── Rate Limiter ─────────────────────────────────────────────────────────────
# Simple in-memory rate limiter used by GUI and Dashboard APIs.

class RateLimiter:
    """Token-bucket-style rate limiter keyed by client identifier (e.g., IP).

    Usage:
        limiter = RateLimiter(max_requests=30, window_seconds=60)

        if limiter.is_allowed("127.0.0.1"):
            handle_request()
        else:
            return HTTP 429
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: Dict[str, List[float]] = {}

    def is_allowed(self, client_id: str) -> bool:
        """Check if a request from this client is within the rate limit."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Clean expired entries
        timestamps = self._buckets.get(client_id, [])
        timestamps = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= self.max_requests:
            return False

        timestamps.append(now)
        self._buckets[client_id] = timestamps
        return True


# ── Audit Logger ─────────────────────────────────────────────────────────────
# Shared audit log buffer used by GUI and Dashboard.

class AuditLog:
    """In-memory audit log with a maximum entry limit.

    Usage:
        audit = AuditLog(max_entries=500)
        audit.record("permission_change", "execute_commands=True", ip="127.0.0.1")
        recent = audit.recent(count=20)
    """

    def __init__(self, max_entries: int = 500):
        self.max_entries = max_entries
        self._entries: List[dict] = []

    def record(self, action: str, detail: str, ip: str = "") -> None:
        """Add an audit entry."""
        entry = {
            "ts": time.time(),
            "action": action,
            "detail": detail,
            "ip": ip,
        }
        self._entries.append(entry)
        logger.info(f"[AUDIT] {action}: {detail}")

        # Trim to prevent unbounded growth
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]

    def recent(self, count: int = 50) -> list:
        """Return the most recent audit entries."""
        return self._entries[-count:]
