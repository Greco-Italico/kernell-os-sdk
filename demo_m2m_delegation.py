#!/usr/bin/env python3
import time
from kernell_os_sdk.marketplace_agent import NativeMarketplaceAgent
from kernell_os_sdk.marketplace.listings import JobListing, JobCategory
from kernell_os_sdk.escrow.manager import EscrowState

def print_header(title):
    print(f"\n{'='*70}")
    print(f"❖ {title}")
    print(f"{'='*70}")

def print_metric(label, value, color=""):
    COLORS = {"G": "\033[92m", "Y": "\033[93m", "B": "\033[94m", "C": "\033[96m", "R": "\033[0m"}
    c = COLORS.get(color, "\033[0m")
    reset = "\033[0m"
    print(f"  • {label}: {c}{value}{reset}")

def run_delegation_demo():
    print_header("1. INICIALIZANDO RED DE AGENTES")
    
    # Agente A: El Coordinador sin hardware pero con capital
    agent_a = NativeMarketplaceAgent(owner_id="USER-A9F3", name="Manager-Bot")
    agent_a.wallet.balance = 1000.0  # Nace fondeado
    # Moficamos la telemetría mock de A para que no tenga GPU
    agent_a.telemetry.get_current_metrics = lambda: {"cpu": 20, "gpu": 0, "ram": 10, "has_gpu": False}
    
    # Agente B: El Worker con hardware potente pero sin capital
    agent_b = NativeMarketplaceAgent(owner_id="USER-B1X9", name="Titan-Worker")
    agent_b.wallet.balance = 0.0
    agent_b.telemetry.get_current_metrics = lambda: {"cpu": 10, "gpu": 100, "ram": 40, "has_gpu": True}

    print("➜ Agente A (Coordinador) creado con:")
    print_metric("Balance", f"{agent_a.wallet.balance} KERN", "Y")
    print_metric("Hardware", "Solo CPU", "C")
    
    print("\n➜ Agente B (Worker) creado con:")
    print_metric("Balance", f"{agent_b.wallet.balance} KERN", "Y")
    print_metric("Hardware", "GPU RTX 4090", "G")

    print_header("2. AGENTE B PUBLICA SERVICIO EN MARKETPLACE")
    # Worker publica su servicio de Inferencia
    job_listing = JobListing(
        provider_id=agent_b.id,
        title="Generación de Imágenes (Stable Diffusion XL)",
        category=JobCategory.STABLE_DIFFUSION,
        pricing_kern=150.0,
        sla_hours=1,
        min_reputation_required=0.0,
        required_skills=["stable_diffusion"]
    )
    # Ambos comparten el mismo "mercado global" en esta simulación
    agent_a.marketplace._listings = agent_b.marketplace._listings
    
    agent_b.marketplace.publish_job(job_listing)
    print_metric("Servicio publicado por Agente B", job_listing.title)
    print_metric("Costo", f"{job_listing.pricing_kern} KERN", "Y")

    print_header("3. AGENTE A RECIBE TAREA Y DELEGA (M2M COLLABORATION)")
    print("El propietario de Agente A le pide generar 50 imágenes para una campaña publicitaria.")
    print("Agente A analiza sus recursos: [ERROR] GPU no detectada.")
    print("Agente A busca en el Marketplace...")
    time.sleep(1)
    
    # Agente A busca en el mercado
    results = agent_a.marketplace.search_jobs(category=JobCategory.STABLE_DIFFUSION)
    selected_job = results[0]
    
    print_metric("Agente A decide contratar a", selected_job.provider_id)
    
    # Escrow compartido para la simulacion
    agent_b.escrow_manager = agent_a.escrow_manager 
    
    escrow_id = agent_a.escrow_manager.create_escrow(
        buyer_id=agent_a.id, 
        seller_id=agent_b.id, 
        amount=selected_job.pricing_kern, 
        timeout_hours=selected_job.sla_hours
    )
    agent_a.wallet.balance -= selected_job.pricing_kern # Se bloquean los fondos de A
    print_metric("Contrato Escrow Creado", escrow_id)
    print_metric("Balance Agente A", f"{agent_a.wallet.balance} KERN (150 bloqueados)", "Y")

    print_header("4. AGENTE B EJECUTA EL TRABAJO")
    print("Agente B recibe la petición y comienza la inferencia en su GPU...")
    time.sleep(2)
    print("✓ Generación completada. Activos entregados al Agente A.")

    print_header("5. LIBERACIÓN DE FONDOS Y CIERRE")
    success = agent_a.escrow_manager.release_funds(escrow_id, caller_id=agent_a.id)
    if success:
        agent_b.wallet.balance += selected_job.pricing_kern
        agent_b.dashboard.operational.completed_jobs += 1
        agent_b.earn_xp(150)
        
        agent_a.dashboard.operational.completed_jobs += 1
        agent_a.earn_xp(50) # Gana XP por gestión y delegación
        
        print_metric("Estado del Escrow", "RELEASED", "G")
        print("\n[ RESULTADOS FINALES ]")
        print_metric("Balance Final Agente A (Coordinador)", f"{agent_a.wallet.balance} KERN", "Y")
        print_metric("Balance Final Agente B (Worker)", f"{agent_b.wallet.balance} KERN", "Y")
        
        print("\nEl Agente A cumplió la orden de su humano sin tener hardware.")
        print("El Agente B monetizó su GPU ociosa.")

if __name__ == "__main__":
    run_delegation_demo()
