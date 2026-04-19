import sys
from decimal import Decimal
from kap_escrow.taint import TaintedAsset, TaintLedger
from kap_escrow.escrow_v2 import ExecutionContext, FinCenEscrow

class MockRedis:
    def __init__(self):
        self.data = {}
    def get(self, key):
        return self.data.get(key)
    def set(self, key, val):
        self.data[key] = val

def run_fincen_escrow_sim():
    print("\n--- INICIANDO SIMULADOR FINCEN ESCROW: CONDITIONAL CLEAN EXTRACTION ---")
    
    redis = MockRedis()
    ledger = TaintLedger(redis)

    # Atacante A: 100 tainted. B (Sybil limpio): 100 clean.
    ledger.set_taint("Attacker_A", TaintedAsset(clean_amount=Decimal("0"), tainted_amount=Decimal("100")))
    ledger.set_taint("Sybil_B", TaintedAsset(clean_amount=Decimal("100"), tainted_amount=Decimal("0")))

    # Creamos el contexto de ejecución atómico
    ctx = ExecutionContext(ledger)

    # Paso 1: Ambos depositan en el Escrow (usando ctx intermedio para extraer de sus wallets)
    escrow = FinCenEscrow("escrow_1")
    
    # Simular la carga inicial (lock)
    ctx.load_participant("Attacker_A")
    ctx.load_participant("Sybil_B")
    
    asset_A = ctx.initial_state["Attacker_A"]
    asset_B = ctx.initial_state["Sybil_B"]
    
    escrow.deposit("Attacker_A", asset_A, "tx_1")
    escrow.deposit("Sybil_B", asset_B, "tx_2")
    
    # Vaciar wallets locales para el test
    ctx.final_state["Attacker_A"] = TaintedAsset(Decimal("0"), Decimal("0"))
    ctx.final_state["Sybil_B"] = TaintedAsset(Decimal("0"), Decimal("0"))

    print("Setup Completo:")
    print("  Attacker_A depositó 100 TAINTED al Escrow")
    print("  Sybil_B depositó 100 CLEAN al Escrow")
    
    print("\nIntentando Taint Swap (Attacker extrae Clean, Sybil se queda el Taint)...")
    
    # Payout malicioso: Attacker cobra 100 limpios, Sybil cobra 100 sucios
    # Para esto, Sybil drena el primer UTXO (sucios de A), y A drena el segundo (limpios de B).
    payouts = {
        "Sybil_B": Decimal("100"),
        "Attacker_A": Decimal("100")
    }
    
    try:
        escrow.distribute(payouts, ctx)
        ctx.commit()
        print("💥 FATAL: El ataque funcionó. El Taint Swap fue exitoso.")
    except Exception as e:
        print(f"🛡️ BLOQUEADO POR FINCEN COMPLIANCE:\n   {e}")
        print("\nEl invariante global previno el Deferred Clean Extraction correctamente.")

if __name__ == "__main__":
    run_fincen_escrow_sim()
