#!/usr/bin/env python3
import time
from kernell_os_sdk.marketplace_agent import NativeMarketplaceAgent
from kernell_os_sdk.marketplace.listings import JobListing, JobCategory
from kernell_os_sdk.escrow.manager import EscrowState

def print_header(title):
    print(f"\n{'='*60}")
    print(f"❖ {title}")
    print(f"{'='*60}")

def print_metric(label, value, color=""):
    # ANSI Colors para demos en terminal
    COLORS = {"G": "\033[92m", "Y": "\033[93m", "B": "\033[94m", "R": "\033[0m"}
    c = COLORS.get(color, "\033[0m")
    reset = "\033[0m"
    print(f"  • {label}: {c}{value}{reset}")

def run_demo():
    print_header("1. INICIALIZANDO NATIVE MARKETPLACE AGENT")
    # Agente: "Titan-GPU-01"
    agent = NativeMarketplaceAgent(owner_id="USER-A9F3", name="Titan-GPU-01")
    agent.wallet.balance = 0.0  # Nace en 0
    print_metric("Agente ID", agent.id)
    print_metric("Nombre", agent.name)
    print_metric("Propietario", agent.owner_id)
    print_metric("Balance Inicial", f"{agent.wallet.balance} KERN", "Y")
    
    print_header("2. EJECUCIÓN DE BENCHMARKS Y VERIFICACIÓN DE HARDWARE")
    print("Corriendo suite de benchmarks de Kernell OS...")
    time.sleep(1)
    bench_results = agent.benchmarks.run_full_suite()
    print_metric("CPU Score", bench_results["cpu_score"], "G")
    print_metric("GPU Score", bench_results["gpu_score"], "G")
    print_metric("Network Score", bench_results["network_score"], "G")
    
    # El benchmark desbloquea skills
    if bench_results["gpu_score"] > 90.0:
        agent.verified_skills.append("blender_render")
        agent.verified_skills.append("ffmpeg_encoding")
        print("✓ Skills verificadas añadidas: Blender, FFmpeg")

    print_header("3. PUBLICANDO SERVICIO EN EL MARKETPLACE")
    job = JobListing(
        provider_id=agent.id,
        title="Renderizado 4K Rápido (RTX 4090)",
        category=JobCategory.GPU_RENDER,
        pricing_kern=250.0,
        sla_hours=2,
        min_reputation_required=0.0,
        required_skills=["blender_render"]
    )
    job_id = agent.marketplace.publish_job(job)
    print_metric("Servicio Publicado", job.title)
    print_metric("Pricing", f"{job.pricing_kern} KERN", "Y")
    print_metric("SLA", f"{job.sla_hours} horas")

    print_header("4. SIMULACIÓN DE CONTRATACIÓN (M2M ESCROW)")
    buyer_id = "AGENT-BUYER-99X"
    print(f"Agente comprador ({buyer_id}) contrata el servicio de Renderizado.")
    escrow_id = agent.escrow_manager.create_escrow(
        buyer_id=buyer_id, 
        seller_id=agent.id, 
        amount=job.pricing_kern, 
        timeout_hours=job.sla_hours
    )
    print_metric("Contrato Escrow Creado", escrow_id)
    print_metric("Estado del Escrow", "LOCKED", "Y")
    
    print_header("5. EJECUCIÓN DEL TRABAJO Y LIBERACIÓN DE FONDOS")
    print("Renderizando video en contenedor seguro... [||||||||||100%]")
    time.sleep(1)
    
    # El comprador libera los fondos al estar satisfecho
    success = agent.escrow_manager.release_funds(escrow_id, caller_id=buyer_id)
    if success:
        agent.wallet.balance += job.pricing_kern
        print_metric("Estado del Escrow", "RELEASED", "G")
        print_metric("Nuevo Balance", f"{agent.wallet.balance} KERN", "Y")
        
        # Actualizar métricas operativas
        agent.dashboard.operational.completed_jobs += 1
        agent.dashboard.operational.sla_fulfilled += 1
        agent.dashboard.operational.avg_delivery_time_hours = 0.5 # Completado en 30 mins
        agent.dashboard.operational.gpu_usage_percent = 15.0 # Aún queda mucha GPU libre
        
        # Actualizar métricas financieras
        agent.dashboard.financial.total_revenue += job.pricing_kern
        agent.dashboard.financial.daily_revenue += job.pricing_kern
        agent.dashboard.financial.revenue_by_category[JobCategory.GPU_RENDER.value] = job.pricing_kern
        
        # Simular Review 5 Estrellas
        agent.reputation_engine.update_metrics(agent.id, {
            "quality_score": 98.0,
            "uptime_score": 100.0,
            "sla_compliance": 100.0,
            "benchmark_score": 95.0,
            "task_volume": 10.0,
            "disputes_penalties": 0.0
        })
        
        # Ganar XP y subir de nivel
        agent.earn_xp(250)

    print_header("6. DASHBOARD DE CRECIMIENTO: REPORTE FINAL")
    profile = agent.show_profile()
    
    # Financials & Ops
    print("\n[ Métricas Financieras y Operativas ]")
    print_metric("Ingresos de Hoy", f"{agent.dashboard.financial.daily_revenue} KERN", "Y")
    print_metric("Ingresos GPU Render", f"{agent.dashboard.financial.revenue_by_category.get(JobCategory.GPU_RENDER.value, 0)} KERN")
    print_metric("Uptime", "100%", "G")
    print_metric("Score Global (Reputación)", f"{profile['dynamic_data']['global_reputation']:.2f}/100", "G")
    print_metric("Nivel de Agente", f"{profile['dynamic_data']['level']} (XP: {profile['dynamic_data']['xp']})", "B")
    
    print("\n[ Sugerencias de Crecimiento Generadas por IA ]")
    recs = profile["growth_recommendations"]
    for i, rec in enumerate(recs, 1):
        print(f"  💡 {rec}")
        
    # Añadir sugerencia custom para el demo
    print(f"  💡 Tu benchmark de GPU desbloquea nuevas categorías. Te sugerimos publicar servicios de Stable Diffusion o Inferencia LLM para maximizar tu ROI.")

if __name__ == "__main__":
    run_demo()
