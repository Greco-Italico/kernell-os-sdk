import sys
import os
import json
from decimal import Decimal
from kap_escrow.taint import TaintedAsset, merge_assets, split_asset, TaintLedger

# Mock Redis for Simulator
class MockRedis:
    def __init__(self):
        self.data = {}
    def get(self, key):
        return self.data.get(key)
    def set(self, key, val):
        self.data[key] = val

def run_sybil_dilution_attack():
    """
    Simula el ataque "Iterative Dilution Loop" de Sybil.
    Comprueba si el "Mass Conservation" bloquea la pérdida de taint real.
    """
    print("\n--- INICIANDO SIMULADOR DE ATAQUE SYBIL: DILUCION DE TAINT ---")
    redis = MockRedis()
    ledger = TaintLedger(redis)

    # Setup: Atacante tiene 100 de mass tainted
    ledger.set_taint("attacker", TaintedAsset(clean_amount=Decimal("0"), tainted_amount=Decimal("100")))
    
    # Sybils tienen fondos limpios (100 cada uno para mezclar)
    for i in range(1, 11):
        ledger.set_taint(f"sybil_{i}", TaintedAsset(clean_amount=Decimal("100"), tainted_amount=Decimal("0")))

    print("Estado inicial:")
    print(f"  Atacante: {ledger.get_taint('attacker').total_amount} fondos (Taint ratio: {ledger.get_taint('attacker').taint_ratio})")

    current_holder = "attacker"
    
    for i in range(1, 11):
        sybil = f"sybil_{i}"
        holder_asset = ledger.get_taint(current_holder)
        
        print(f"\n[Ciclo {i}]")
        print(f"  Intentando mover la mitad de los fondos de {current_holder} a {sybil} para mezclarlos.")
        
        # El atacante mueve la mitad de sus fondos al Sybil
        amount_to_move = holder_asset.total_amount / 2
        
        res = ledger.transfer_with_taint(current_holder, sybil, amount_to_move)
        
        if res["status"] == "blocked":
            print(f"  ❌ ATAQUE BLOQUEADO POR EL MOTOR: {res['reason']}")
            break
            
        print(f"  ✅ Transferencia aceptada.")
        sybil_asset = ledger.get_taint(sybil)
        print(f"  Nuevo estado en {sybil}: Total={sybil_asset.total_amount}, Tainted Mass={sybil_asset.tainted_amount}, Ratio={sybil_asset.taint_ratio:.4f}")
        
        current_holder = sybil
        
    print("\n--- RESULTADO FINAL DEL SIMULADOR ---")
    final_asset = ledger.get_taint(current_holder)
    print(f"El holder final ({current_holder}) terminó con:")
    print(f"Total: {final_asset.total_amount}")
    print(f"Tainted Mass INTACTO: {final_asset.tainted_amount}")
    print(f"Ratio de taint: {final_asset.taint_ratio:.4f}")
    
    if final_asset.tainted_amount < Decimal("50"):
        print("💥 EL ATAQUE FUNCIONÓ: La masa tainted fue destruida o diluida mágicamente.")
    else:
        print("🛡️ EL ATAQUE FALLÓ: La masa tainted se conservó matemáticamente. Es imposible lavarlo iterativamente.")

if __name__ == "__main__":
    run_sybil_dilution_attack()
