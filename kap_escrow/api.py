from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from decimal import Decimal
import redis
import os
import uuid

from kap_escrow.taint import TaintLedger, TaintedAsset
from kap_escrow.escrow_v2 import FinCenEscrow, ExecutionContext

app = FastAPI(
    title="Kernell Payments API",
    description="The financial infrastructure for autonomous agents. FinCEN-grade compliant escrows.",
    version="1.0.0"
)

# Dependency to get Redis client
def get_redis():
    r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, db=0, decode_responses=True)
    yield r
    r.close()

# Dependency to get TaintLedger
def get_ledger(r: redis.Redis = Depends(get_redis)):
    return TaintLedger(r)

# Global in-memory mock for Escrows (In prod, serialize FinCenEscrow to Redis)
ACTIVE_ESCROWS = {}

class EscrowCreate(BaseModel):
    sender: str
    receiver: str
    amount: str
    contract_id: str

class EscrowSettle(BaseModel):
    contract_id: str
    payouts: dict[str, str]  # Example: {"agent_A": "50.0", "agent_B": "50.0"}

class MintRequest(BaseModel):
    agent_id: str
    amount: str
    is_tainted: bool = False

@app.post("/dev/mint")
def dev_mint(req: MintRequest, ledger: TaintLedger = Depends(get_ledger)):
    """DEV ONLY: Mints local KERN for an agent."""
    asset = ledger.get_taint(req.agent_id)
    mint_amount = Decimal(req.amount)
    
    clean = asset.clean_amount + (mint_amount if not req.is_tainted else Decimal("0"))
    tainted = asset.tainted_amount + (mint_amount if req.is_tainted else Decimal("0"))
    
    new_asset = TaintedAsset(clean, tainted, "mint_tx")
    ledger.set_taint(req.agent_id, new_asset)
    return {"status": "ok", "agent": req.agent_id, "new_total": str(new_asset.total_amount)}

@app.post("/escrow/create")
def create_escrow(req: EscrowCreate, ledger: TaintLedger = Depends(get_ledger)):
    """Creates a Taint-Aware UTXO Escrow and locks funds."""
    if req.contract_id in ACTIVE_ESCROWS:
        raise HTTPException(status_code=400, detail="Escrow already exists")

    amount = Decimal(req.amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    sender_asset = ledger.get_taint(req.sender)
    if sender_asset.total_amount < amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Escrow Setup
    escrow = FinCenEscrow(req.contract_id)
    ctx = ExecutionContext(ledger)
    
    # Simulate execution context locking funds
    ctx.load_participant(req.sender)
    from kap_escrow.taint import split_asset
    
    # Remove funds from sender's wallet to lock in escrow
    transferred = split_asset(ctx.initial_state[req.sender], amount)
    new_sender = TaintedAsset(
        ctx.initial_state[req.sender].clean_amount - transferred.clean_amount,
        ctx.initial_state[req.sender].tainted_amount - transferred.tainted_amount
    )
    
    # Save the escrow state and commit sender's deduction
    escrow.deposit(req.sender, transferred, f"lock_{req.contract_id}")
    ACTIVE_ESCROWS[req.contract_id] = escrow
    
    ledger.set_taint(req.sender, new_sender)

    return {"status": "escrow_created", "contract_id": req.contract_id, "locked_amount": str(amount)}

@app.post("/escrow/settle")
def settle_escrow(req: EscrowSettle, ledger: TaintLedger = Depends(get_ledger)):
    """Resolves an escrow, enforces invariants, and distributes UTXOs."""
    if req.contract_id not in ACTIVE_ESCROWS:
        raise HTTPException(status_code=404, detail="Escrow not found")

    escrow = ACTIVE_ESCROWS[req.contract_id]
    ctx = ExecutionContext(ledger)
    
    payouts_decimal = {k: Decimal(v) for k, v in req.payouts.items()}
    
    try:
        escrow.distribute(payouts_decimal, ctx)
        ctx.commit()  # Will throw Exception if Compliance Violation
        
        # Cleanup
        del ACTIVE_ESCROWS[req.contract_id]
        
        return {"status": "settled", "contract_id": req.contract_id}
        
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Compliance/Execution Error: {str(e)}")

@app.get("/compliance/verify/{agent_id}")
def verify_compliance(agent_id: str, ledger: TaintLedger = Depends(get_ledger)):
    """Returns the agent's compliance status and taint mass."""
    asset = ledger.get_taint(agent_id)
    ratio = asset.taint_ratio
    
    status = "clean"
    if ratio >= Decimal("0.20"):
        status = "blocked_tainted"
    elif ratio >= Decimal("0.05"):
        status = "warning_tainted"
        
    return {
        "agent_id": agent_id,
        "status": status,
        "taint_ratio": str(ratio),
        "clean_mass": str(asset.clean_amount),
        "tainted_mass": str(asset.tainted_amount),
        "total_mass": str(asset.total_amount)
    }

@app.get("/balance/{agent_id}")
def get_balance(agent_id: str, ledger: TaintLedger = Depends(get_ledger)):
    asset = ledger.get_taint(agent_id)
    return {"agent_id": agent_id, "balance": str(asset.total_amount)}
