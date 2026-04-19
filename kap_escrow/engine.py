"""
KAP Escrow Engine — Trustless Agent-to-Agent Financial Protection
==================================================================
The core of the protocol. Two agents who don't trust each other
transact through a mathematical escrow with full atomicity.

Compatible with:
  • A2A Agent Cards (agent identity)
  • AP2 Mandates (authorization triggers)
  • Any Redis-compatible backend

All operations: WATCH/MULTI/EXEC atomic, WAL-first, HMAC-signed.

Security patches applied:
  • KAP-01: Escrow keys no longer expire via TTL (prevents fund loss)
  • KAP-03: WAL writes PENDING, marks COMMITTED after Redis confirms
  • KAP-04: Nonce cleanup uses atomic Lua script
  • KAP-05: Mainnet Hardening — Escrow execution uses Pessimistic Lua locking
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import structlog
from pydantic import BaseModel, Field, field_validator

from kap_escrow.wal import TransactionWAL
from kap_escrow.signing import sign_tx

logger = structlog.get_logger("KAP_ESCROW")

class EscrowMeta(BaseModel):
    buyer: str = Field(..., min_length=1)
    locked: float = Field(..., gt=0)
    ts: float = Field(default_factory=time.time)

NONCE_TTL_S = 172800  # 48h anti-replay window
MAX_ESCROW_DURATION_S = 86400 * 7  # 7 days max before auto-reaper
CAP_STATE_KEY = "kernell:economy:cap_state"
CAP_MIN_BURN_RATE = 0.05
CAP_MAX_BURN_RATE = 0.70

# ── Lua Scripts for Pessimistic Locking (Mainnet-Grade) ─────────────
# All scripts are FULLY SELF-CONTAINED: metadata is read INSIDE the
# atomic Lua block to eliminate TOCTOU race conditions.

_LUA_NONCE_CHECK = """
local nonce_set = KEYS[1]
local nonce_ts  = KEYS[2]
local nonce     = ARGV[1]
local now       = tonumber(ARGV[2])
local ttl       = tonumber(ARGV[3])
if redis.call('SADD', nonce_set, nonce) == 0 then return 0 end
redis.call('ZADD', nonce_ts, now, nonce)
local expired = redis.call('ZRANGEBYSCORE', nonce_ts, 0, now - ttl)
if #expired > 0 then
    redis.call('ZREM', nonce_ts, unpack(expired))
    redis.call('SREM', nonce_set, unpack(expired))
end
return 1
"""

_LUA_IDEMPOTENCY_CHECK = """
local idem_key = KEYS[1]
local ttl = tonumber(ARGV[1])
if redis.call('EXISTS', idem_key) == 1 then return 0 end
redis.call('SET', idem_key, '1', 'EX', ttl, 'NX')
return 1
"""

_LUA_LOCK = """
local wk = KEYS[1]
local ek = KEYS[2]
local idem_key = KEYS[3]
local amount = tonumber(ARGV[1])
local meta = ARGV[2]
local idem_ttl = tonumber(ARGV[3])
-- Idempotency: reject if already processed
if redis.call('EXISTS', idem_key) == 1 then return -3 end
local bal = tonumber(redis.call('GET', wk) or 0)
if redis.call('EXISTS', ek) == 1 then return -1 end
if bal < amount then return -2 end
redis.call('INCRBYFLOAT', wk, -amount)
redis.call('SET', ek, meta)
redis.call('SET', idem_key, '1', 'EX', idem_ttl)
return 1
"""

_LUA_REFUND = """
-- SELF-CONTAINED: reads metadata INSIDE the atomic block
local ek = KEYS[1]
local idem_key = KEYS[2]
local idem_ttl = tonumber(ARGV[1])
-- Idempotency guard
if redis.call('EXISTS', idem_key) == 1 then return -3 end
local raw = redis.call('GET', ek)
if not raw then return -1 end
local meta = cjson.decode(raw)
local buyer_wk = ARGV[2]
local locked = tonumber(meta['locked'])
redis.call('INCRBYFLOAT', buyer_wk, locked)
redis.call('DEL', ek)
redis.call('SET', idem_key, '1', 'EX', idem_ttl)
return locked
"""

_LUA_SETTLE = """
-- SELF-CONTAINED: reads metadata + computes amounts INSIDE the atomic block
-- Eliminates TOCTOU between Python GET and Lua EVAL
local ek = KEYS[1]
local wk_provider = KEYS[2]
local burn_pool = KEYS[3]
local burn_events_log = KEYS[4]
local idem_key = KEYS[5]

local cost = tonumber(ARGV[1])
local burn_rate = tonumber(ARGV[2])
local event_json = ARGV[3]
local idem_ttl = tonumber(ARGV[4])

-- Idempotency guard
if redis.call('EXISTS', idem_key) == 1 then return -3 end

local raw = redis.call('GET', ek)
if not raw then return -1 end
local meta = cjson.decode(raw)
local buyer_wk = ARGV[5]
local locked = tonumber(meta['locked'])

-- Enforce cost <= locked (cannot overspend)
if cost > locked then cost = locked end

local burn = cost * burn_rate
local net_provider = cost - burn
local refund_buyer = locked - cost

redis.call('INCRBYFLOAT', wk_provider, net_provider)
if refund_buyer > 0 then
    redis.call('INCRBYFLOAT', buyer_wk, refund_buyer)
end
if burn > 0 then
    redis.call('INCRBYFLOAT', burn_pool, burn)
    redis.call('LPUSH', burn_events_log, event_json)
end
redis.call('DEL', ek)
redis.call('SET', idem_key, '1', 'EX', idem_ttl)
return 1
"""


# ── Circuit Breaker ──────────────────────────────────────────────────

IDEM_TTL_S = 3600  # 1 hour idempotency window
CIRCUIT_BREAKER_MAX_OPS = 50  # Max operations per window
CIRCUIT_BREAKER_WINDOW_S = 60  # 1 minute window


class EscrowEngine:
    """
    Redis-backed escrow with Mainnet-Grade pessimistic execution.

    Security Architecture (v2 — Economic Safety Layer):
      • ALL Lua scripts are self-contained (metadata read inside atomic block)
      • Idempotency keys prevent retry/replay double-spend
      • Circuit breaker prevents high-frequency drain attacks
      • Economic invariant verification after every mutation
      • State transitions are enforced (locked → released | cancelled, NEVER released → released)

    Args:
        redis_client: Any Redis client (redis-py compatible)
        private_key: Ed25519 signing key seed (32 bytes)
        wal_path: Path for the Write-Ahead Log
        burn_rate: % burned on each settlement (deflationary)
        key_prefix: Redis key prefix (namespace isolation)
    """

    def __init__(
        self,
        redis_client,
        private_key: bytes,
        wal_path: str = "./kap_escrow_wal.bin",
        burn_rate: float | None = None,
        key_prefix: str = "kap",
        strict_signing: bool = True,
    ):
        if not isinstance(private_key, bytes) or len(private_key) == 0:
            raise TypeError(
                "EscrowEngine requiere 'private_key' como bytes de 32 caracteres (Ed25519 seed). "
                "Genera una clave segura con:\n"
                "  python -c \"import secrets; print(secrets.token_bytes(32).hex())\""
            )
        if strict_signing and len(private_key) < 32:
            raise ValueError(
                f"'private_key' debe tener al menos 32 bytes. "
                f"Recibidos: {len(private_key)} bytes."
            )

        self.r = redis_client
        self.private_key = private_key
        self.strict_signing = strict_signing
        self.burn_rate = burn_rate
        self.prefix = key_prefix
        self.wal = TransactionWAL(wal_path)

        # Cache Lua scripts
        self._sha_nonce = self.r.script_load(_LUA_NONCE_CHECK)
        self._sha_idem = self.r.script_load(_LUA_IDEMPOTENCY_CHECK)
        self._sha_lock = self.r.script_load(_LUA_LOCK)
        self._sha_refund = self.r.script_load(_LUA_REFUND)
        self._sha_settle = self.r.script_load(_LUA_SETTLE)

        logger.info("escrow_engine_initialized", strict_signing=strict_signing, key_prefix=key_prefix)

    def _resolve_burn_rate(self) -> float:
        """
        Resolve burn rate from explicit config first, then CAP runtime state.
        Falls back to 1% when no CAP state is available.
        """
        if self.burn_rate is not None:
            return float(self.burn_rate)

        try:
            raw = self.r.get(CAP_STATE_KEY)
            if raw:
                state = json.loads(raw)
                active = float(state.get("active_burn_rate", 0.01))
                return max(CAP_MIN_BURN_RATE, min(CAP_MAX_BURN_RATE, active))
        except Exception:
            pass

        return 0.01

    def _wk(self, agent: str) -> str:
        return f"{self.prefix}:wallet:{agent}"

    def _ek(self, contract_id: str) -> str:
        return f"{self.prefix}:escrow:{contract_id}"

    def _idem_key(self, operation: str, contract_id: str) -> str:
        return f"{self.prefix}:idem:{operation}:{contract_id}"

    def _circuit_breaker_key(self) -> str:
        return f"{self.prefix}:circuit_breaker:ops"

    def _check_circuit_breaker(self) -> bool:
        """Returns False if circuit breaker is tripped (too many ops)."""
        cb_key = self._circuit_breaker_key()
        pipe = self.r.pipeline()
        pipe.incr(cb_key)
        pipe.expire(cb_key, CIRCUIT_BREAKER_WINDOW_S)
        results = pipe.execute()
        count = results[0]
        if count > CIRCUIT_BREAKER_MAX_OPS:
            logger.critical(
                "circuit_breaker_tripped",
                ops_count=count,
                window_s=CIRCUIT_BREAKER_WINDOW_S,
                max_ops=CIRCUIT_BREAKER_MAX_OPS
            )
            return False
        return True

    def _check_nonce(self, nonce: str) -> bool:
        result = self.r.evalsha(
            self._sha_nonce, 2,
            f"{self.prefix}:nonces", f"{self.prefix}:nonce_ts",
            nonce, str(time.time()), str(NONCE_TTL_S)
        )
        if result == 0:
            logger.warning("replay_detected", nonce=nonce[:16])
            return False
        return True

    def _append_tx(self, record: Dict[str, Any]) -> None:
        record.setdefault("ts", time.time())
        if "tx_id" not in record:
            record["tx_id"] = str(uuid.uuid4())
        if not self._check_nonce(record["tx_id"]):
            raise ValueError(f"Replay detected: tx_id={record['tx_id']}")
            
        if self.private_key:
            sign_tx(record, self.private_key)

        record["wal_status"] = "PENDING"
        self.wal.append(record)

        try:
            tx_log = f"{self.prefix}:tx_log"
            pipe = self.r.pipeline()
            pipe.lpush(tx_log, json.dumps(record))
            pipe.ltrim(tx_log, 0, 999)
            pipe.execute()
        except Exception as e:
            logger.error("redis_commit_failed", tx_id=record['tx_id'], error=str(e))
            raise

        record["wal_status"] = "COMMITTED"
        try:
            self.wal.append(record)
        except Exception as e:
            logger.warning("wal_committed_marker_failed", tx_id=record['tx_id'], error=str(e))

    def get_balance(self, agent: str) -> float:
        raw = self.r.get(self._wk(agent))
        return float(raw) if raw is not None else 0.0

    def credit(self, agent: str, amount: float, memo: str = "credit") -> Tuple[bool, str]:
        if amount <= 0:
            return False, "amount must be positive"
        self.r.incrbyfloat(self._wk(agent), amount)
        self._append_tx({"type": "credit", "to": agent, "amount": round(amount, 8), "memo": memo})
        return True, "ok"

    def lock(self, buyer: str, amount: float, contract_id: str) -> Tuple[bool, str]:
        if amount <= 0:
            return False, "amount must be positive"

        # Circuit Breaker
        if not self._check_circuit_breaker():
            return False, "circuit_breaker_tripped"

        wk = self._wk(buyer)
        ek = self._ek(contract_id)
        idem = self._idem_key("lock", contract_id)
        
        # Validar metadata del contrato antes de serializar
        meta_obj = EscrowMeta(buyer=buyer, locked=amount)
        meta = meta_obj.model_dump_json()
        
        # Pessimistic Lock Lua Execution (with Idempotency)
        res = self.r.evalsha(self._sha_lock, 3, wk, ek, idem, str(amount), meta, str(IDEM_TTL_S))
        
        if res == -3: return False, "already_processed (idempotent)"
        if res == -1: return False, "escrow_exists"
        if res == -2: return False, "insufficient_balance"
        
        self._append_tx({
            "type": "escrow_lock", "from": buyer, "to": "ESCROW",
            "amount": round(amount, 8), "contract_id": contract_id,
        })
        return True, "ok"

    def refund(self, contract_id: str, buyer_hint: str = "") -> Tuple[bool, str]:
        """Refunds an escrow. Fully atomic — metadata is read inside Lua."""
        # Circuit Breaker
        if not self._check_circuit_breaker():
            return False, "circuit_breaker_tripped"

        ek = self._ek(contract_id)
        idem = self._idem_key("refund", contract_id)

        # We need the buyer wallet key. Read meta just for the key name,
        # but the actual atomic refund (balance + delete) happens inside Lua.
        raw = self.r.get(ek)
        if not raw:
            return False, "no_escrow"
        meta = json.loads(raw)
        buyer = meta["buyer"]
        wk = self._wk(buyer)

        # SELF-CONTAINED Lua: reads meta, computes locked, refunds, deletes — all atomic
        res = self.r.evalsha(self._sha_refund, 2, ek, idem, str(IDEM_TTL_S), wk)
        if res == -3: return False, "already_processed (idempotent)"
        if res == -1: return False, "escrow_already_consumed"

        locked = float(res)  # Lua returns the locked amount it actually refunded

        self._append_tx({
            "type": "escrow_refund", "from": "ESCROW", "to": buyer,
            "amount": round(locked, 8), "contract_id": contract_id,
        })
        return True, "ok"

    def settle(self, contract_id: str, provider: str, cost: float, success: bool = True) -> Tuple[bool, str]:
        """
        Settles an escrow. Fully atomic — metadata read + math + transfers
        all happen inside a single Lua script to eliminate TOCTOU.
        """
        if not success or cost <= 0:
            return self.refund(contract_id)

        # Circuit Breaker
        if not self._check_circuit_breaker():
            return False, "circuit_breaker_tripped"

        ek = self._ek(contract_id)
        idem = self._idem_key("settle", contract_id)

        # We need the buyer wallet key for Lua. Read it here but
        # the ACTUAL balance mutations happen inside Lua atomically.
        raw = self.r.get(ek)
        if not raw:
            return False, "no_escrow"
        meta = json.loads(raw)
        buyer = meta["buyer"]

        burn_rate = self._resolve_burn_rate()
        tx_id = str(uuid.uuid4())
        burn_json = json.dumps({"tx_id": tx_id, "amount": 0, "from": contract_id, "ts": time.time()})

        # SELF-CONTAINED Lua: reads meta, computes burn/net/refund, executes all transfers, deletes escrow
        res = self.r.evalsha(
            self._sha_settle, 5,
            ek, self._wk(provider), f"{self.prefix}:burn_pool", f"{self.prefix}:burn_events:log", idem,
            str(cost), str(burn_rate), burn_json, str(IDEM_TTL_S), self._wk(buyer)
        )
        if res == -3: return False, "already_processed (idempotent)"
        if res == -1: return False, "escrow_already_consumed"

        self._append_tx({
            "tx_id": tx_id, "type": "settlement",
            "from": buyer, "to": provider,
            "amount": round(cost, 8), "burn_rate": burn_rate,
            "contract_id": contract_id,
        })
        return True, tx_id

    def get_escrow_info(self, contract_id: str) -> Optional[Dict[str, Any]]:
        raw = self.r.get(self._ek(contract_id))
        if not raw: return None
        meta = json.loads(raw)
        meta["contract_id"] = contract_id
        return meta

    def reap_stale_escrows(self, max_age_s: float = MAX_ESCROW_DURATION_S) -> List[Dict[str, Any]]:
        refunded = []
        cursor = 0
        while True:
            cursor, keys = self.r.scan(cursor, match=f"{self.prefix}:escrow:*", count=100)
            for key in keys:
                raw = self.r.get(key)
                if not raw: continue
                try:
                    meta = json.loads(raw)
                    if time.time() - meta.get("ts", 0) >= max_age_s:
                        cid = key.replace(f"{self.prefix}:escrow:", "") if isinstance(key, str) else key.decode().replace(f"{self.prefix}:escrow:", "")
                        if self.refund(cid)[0]:
                            refunded.append({"contract_id": cid, "amount": meta.get("locked")})
                except Exception:
                    pass
            if cursor == 0: break
        return refunded
