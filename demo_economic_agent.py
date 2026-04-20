import time
from decimal import Decimal
from kernell_os_sdk.identity import create_passport
from kernell_os_sdk.economic_agent import EconomicAgent

def run_demo():
    print("🤖 --- KERNELL NETWORK: ECONOMIC AGENT DEMO --- 🤖\n")

    # 1. Initialize Agents
    print("[1] Inicializando Identidades Nativas (Ed25519)...")
    passport_buyer, _ = create_passport("buyer_agent")
    passport_seller, _ = create_passport("seller_agent")

    buyer = EconomicAgent(passport_buyer, api_url="http://localhost:8000")
    seller = EconomicAgent(passport_seller, api_url="http://localhost:8000")

    print(f"    Buyer Agent ID: {buyer.agent_id[:12]}...")
    print(f"    Seller Agent ID: {seller.agent_id[:12]}...\n")

    # 2. Fund Buyer (Simulation of On-chain deposit to L2)
    print(f"[2] Fondeando Buyer con 100 $KERN locales (0 Gas)...")
    buyer.http.post("http://localhost:8000/dev/mint", json={"agent_id": buyer.agent_id, "amount": "100.0", "is_tainted": False})
    print(f"    Buyer Balance: {buyer.get_balance()} $KERN\n")

    # 3. Security Check (FinCEN Compliance)
    print(f"[3] Buyer verifica la salud financiera (Taint) de Seller...")
    is_safe = buyer.check_counterparty(seller.agent_id)
    if is_safe:
        print("    ✅ Seller está limpio. Riesgo de lavado nulo. Procediendo con negocio.\n")
    
    # 4. Escrow Lock
    price = Decimal("15.0")
    print(f"[4] Buyer contrata 'image_generation' por {price} $KERN...")
    contract_id = buyer.buy_service(target_agent_id=seller.agent_id, service_id="image_generation", amount_kern=price)
    print(f"    🔒 Fondos bloqueados en el contrato: {contract_id}\n")

    time.sleep(2) # Simulate work

    # 5. Settlement
    print("[5] Seller entrega el trabajo y reclama el pago...")
    seller.fulfill_order(contract_id=contract_id, client_agent_id=buyer.agent_id, amount_kern=price, proof_of_work="ipfs://QmHash...")
    print("    ✅ Liquidación atómica completada.\n")

    # 6. Final Balances
    print("[6] Balances Finales L2 (0 Latency):")
    print(f"    Buyer Balance: {buyer.get_balance()} $KERN")
    print(f"    Seller Balance: {seller.get_balance()} $KERN")
    
    print("\n🚀 Transacción de Agente-a-Agente finalizada con éxito y cumplimiento garantizado.")

if __name__ == "__main__":
    try:
        run_demo()
    except Exception as e:
        print(f"\n❌ Error en la Demo: Asegúrate de tener la API corriendo en el puerto 8000.")
        print(f"Detalle: {e}")
