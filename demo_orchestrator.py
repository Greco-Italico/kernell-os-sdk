import time
from decimal import Decimal

from kernell_os_sdk.identity import create_passport
from kernell_os_sdk.economic_agent import EconomicAgent
from kernell_os_sdk.orchestrator import EconomicOrchestrator

def run_orchestrator_demo():
    print("🤖 --- KERNELL NETWORK: ECONOMIC ORCHESTRATOR DEMO --- 🤖\n")

    # 1. Initialize Identities
    passport_buyer, _ = create_passport("ai_orchestrator_01")
    passport_seller, _ = create_passport("image_service_01")

    # 2. Setup Core Agents
    core_buyer = EconomicAgent(passport_buyer, api_url="http://localhost:8000")
    core_seller = EconomicAgent(passport_seller, api_url="http://localhost:8000")

    # 3. Wrap Buyer with Orchestrator Intelligence
    # The seller just stays as a basic Commerce agent for this demo
    orchestrator = EconomicOrchestrator(core_buyer)
    seller_commerce = EconomicOrchestrator(core_seller)

    print(f"[Init] Orchestrator (Buyer) ID:  {core_buyer.agent_id[:12]}")
    print(f"[Init] Service Provider (Seller) ID: {core_seller.agent_id[:12]}\n")

    # Verify Buyer starts broke!
    balance = orchestrator.finance.get_balance()
    print(f"💰 Initial Balance of Orchestrator: {balance} $KERN\n")

    # 4. Orchestrator executes a high-level task
    price = Decimal("25.0")
    
    # This single call triggers the internal Loop:
    # Check Balance -> Sell Compute -> Earn -> Verify Compliance -> Buy Escrow
    contract_id = orchestrator.run_task(
        task_name="Generate Marketing Image",
        required_service="image_generation",
        provider_id=core_seller.agent_id,
        cost=price
    )
    
    if contract_id:
        print(f"\n[Provider] Delivering Image and Settling Contract {contract_id}...")
        seller_commerce.commerce.deliver_service(
            contract_id=contract_id, 
            client_id=core_buyer.agent_id, 
            amount=price, 
            result_data="ipfs://MarketingAsset.png"
        )
        print("✅ Contract Settled.")
        
        final_balance = orchestrator.finance.get_balance()
        print(f"\n💰 Final Balance of Orchestrator: {final_balance} $KERN")
        print("🎉 Mission Accomplished: Agent self-funded and executed autonomously.")

if __name__ == "__main__":
    try:
        run_orchestrator_demo()
    except Exception as e:
        print(f"\n❌ Error en la Demo: {e}")
