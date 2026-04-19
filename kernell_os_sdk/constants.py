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
from collections import OrderedDict
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
COMMAND_SAFELIST = frozenset({
    # Navegación y listado
    "ls", "ll", "la", "pwd", "find", "tree", "du", "df",
    # Lectura de archivos
    "cat", "less", "more", "head", "tail", "grep", "awk", "sed",
    "wc", "diff", "sort", "uniq",
    # Escritura segura (no destructiva)
    "echo", "printf", "touch", "mkdir", "cp", "mv",
    # Red (solo lectura)
    "curl", "wget", "ping", "nslookup", "dig",
    # Desarrollo
    "python3", "python", "pip", "pip3",
    "node", "npm", "npx", "yarn",
    "git",
    # Sistema (solo lectura)
    "whoami", "date", "env", "printenv", "uname",
    "ps", "top", "free", "uptime",
})


# ── Rate Limiter ─────────────────────────────────────────────────────────────
# Simple in-memory rate limiter used by GUI and Dashboard APIs.

class RateLimiter:
    """Rate limiter con límite de IPs únicas para prevenir memory exhaustion."""

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: int = 60,
        max_tracked_clients: int = 10_000,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_tracked_clients = max_tracked_clients
        self._buckets: OrderedDict = OrderedDict()

    def is_allowed(self, client_id: str) -> bool:
        """Check if a request from this client is within the rate limit."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Limpiar cliente más antiguo si se alcanza el límite
        if client_id not in self._buckets and len(self._buckets) >= self.max_tracked_clients:
            # Eliminar el cliente menos reciente (LRU)
            self._buckets.popitem(last=False)

        timestamps = self._buckets.get(client_id, [])
        timestamps = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= self.max_requests:
            return False

        timestamps.append(now)
        self._buckets[client_id] = timestamps
        # Mover al final (más reciente) para LRU
        self._buckets.move_to_end(client_id)
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
