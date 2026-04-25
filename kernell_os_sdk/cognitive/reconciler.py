import time
import logging
from redis import Redis
from decimal import Decimal
from collections import defaultdict

logger = logging.getLogger("kernell.reconciler")

LEDGER_STREAM = "kernell:ledger"
BALANCE_PREFIX = "balance:"

def load_ledger(redis_client: Redis):
    """Carga todo el ledger. Para prod, se debe usar last_id y particionamiento."""
    return redis_client.xrange(LEDGER_STREAM, "-", "+")

def recompute_balances(entries):
    balances = defaultdict(Decimal)
    for _, data in entries:
        src = data.get("from")
        dst = data.get("to")
        amt = Decimal(data.get("amount", "0"))
        if src and dst:
            balances[src] -= amt
            balances[dst] += amt
    return balances

def get_actual_balance(redis_client: Redis, node_id: str) -> Decimal:
    val = redis_client.get(f"{BALANCE_PREFIX}{node_id}")
    return Decimal(val or "0")

def reconcile(redis_client: Redis, dry_run=True):
    entries = load_ledger(redis_client)
    computed = recompute_balances(entries)
    
    mismatches = []
    for node_id, expected in computed.items():
        actual = get_actual_balance(redis_client, node_id)
        if actual != expected:
            mismatches.append((node_id, actual, expected))
            if not dry_run:
                # Alerta: esto sobrescribe sin importar el orden temporal
                redis_client.set(f"{BALANCE_PREFIX}{node_id}", str(expected))
                
    return mismatches

def start_reconciler_loop(redis_url: str):
    client = Redis.from_url(redis_url, decode_responses=True)
    logger.info("Starting automated ledger reconciler...")
    
    while True:
        try:
            mismatches = reconcile(client, dry_run=True)
            if mismatches:
                logger.error(f"⚠️ MISMATCH DETECTED: {len(mismatches)} nodes out of sync!")
                for m in mismatches:
                    logger.error(f"Node: {m[0]}, Actual: {m[1]}, Expected: {m[2]}")
            else:
                logger.debug("✅ Ledger consistent")
        except Exception as e:
            logger.error(f"Reconciler error: {e}")
            
        time.sleep(10)

if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    start_reconciler_loop(os.environ.get("KERNELL_REDIS_URL", "redis://localhost:7001"))
