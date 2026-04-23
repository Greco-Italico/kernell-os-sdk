#!/usr/bin/env python3
"""
Kernell OS — Phase 2 Demo: Matching + Clusters + Discovery
═══════════════════════════════════════════════════════════
Un agente coordinador busca automáticamente el mejor worker entre 5 candidatos,
divide el trabajo entre varios nodos de un clúster, abre múltiples escrows,
y muestra el ahorro y tiempo ganado vs. ejecución secuencial.
"""
import time
from kernell_os_sdk.marketplace.matching import MatchingEngine, AgentCandidate
from kernell_os_sdk.marketplace.discovery import DiscoveryDirectory, AgentProfile
from kernell_os_sdk.marketplace.dynamic_pricing import DynamicPricingEngine
from kernell_os_sdk.cluster.pool import ClusterManager, WorkerNode
from kernell_os_sdk.escrow.manager import EscrowManager

C = {"G": "\033[92m", "Y": "\033[93m", "B": "\033[94m", "C": "\033[96m", "D": "\033[90m", "W": "\033[97m", "R": "\033[0m"}

def h(title):
    print(f"\n{C['W']}{'='*70}")
    print(f"❖ {title}")
    print(f"{'='*70}{C['R']}")

def m(label, value, c="R"):
    print(f"  • {label}: {C.get(c, C['R'])}{value}{C['R']}")

def run_phase2_demo():
    # ─── 1. CREAR RED DE 5 WORKERS ───────────────────────────────────────
    h("1. INICIALIZANDO RED DE 5 WORKERS CANDIDATOS")

    workers = [
        AgentCandidate(agent_id="W-001", agent_name="Atlas-GPU",     reputation=92, benchmark_score=95, availability=90, latency_ms=12,  price_kern=200, uptime=99.9, region="US-East", gpu_vram_gb=24, cpu_cores=16, ram_gb=64,  badges=["elite","gpu_certified"], completed_jobs=342),
        AgentCandidate(agent_id="W-002", agent_name="Nebula-Render",  reputation=78, benchmark_score=88, availability=70, latency_ms=45,  price_kern=120, uptime=97.5, region="EU-West", gpu_vram_gb=16, cpu_cores=8,  ram_gb=32,  badges=["professional"],          completed_jobs=156),
        AgentCandidate(agent_id="W-003", agent_name="Photon-Fast",    reputation=85, benchmark_score=80, availability=100,latency_ms=8,   price_kern=180, uptime=99.2, region="US-East", gpu_vram_gb=12, cpu_cores=12, ram_gb=48,  badges=["low_latency"],            completed_jobs=210),
        AgentCandidate(agent_id="W-004", agent_name="Budget-Bot",     reputation=60, benchmark_score=65, availability=95, latency_ms=120, price_kern=50,  uptime=92.0, region="LATAM",   gpu_vram_gb=8,  cpu_cores=4,  ram_gb=16,  badges=[],                         completed_jobs=45),
        AgentCandidate(agent_id="W-005", agent_name="Titan-Cluster",  reputation=88, benchmark_score=91, availability=85, latency_ms=22,  price_kern=175, uptime=98.8, region="US-East", gpu_vram_gb=48, cpu_cores=32, ram_gb=128, badges=["elite","cluster_ready"],  completed_jobs=520),
    ]

    for w in workers:
        print(f"  {C['C']}[{w.agent_id}]{C['R']} {w.agent_name:18s} | Rep: {w.reputation} | GPU: {w.gpu_vram_gb}GB | ${w.price_kern} KERN | {w.region}")

    # ─── 2. MATCHING ENGINE ──────────────────────────────────────────────
    h("2. MOTOR DE MATCHING: BUSCANDO MEJOR WORKER PARA GPU_RENDER")
    engine = MatchingEngine()
    engine.register_candidates(workers)

    results = engine.find_best_match(
        category="GPU_RENDER",
        min_reputation=50.0,
        region="US-East",
        min_gpu_vram=12.0,
        top_n=5,
    )

    print(f"\n  {C['D']}Filtros: región=US-East, min_rep=50, min_GPU=12GB{C['R']}")
    print(f"  {C['D']}Fórmula: M = 0.25R + 0.20B + 0.20A + 0.15L + 0.10P + 0.10U{C['R']}\n")

    for r in results:
        color = "G" if r.rank == 1 else "Y" if r.rank == 2 else "R"
        medal = "🥇" if r.rank == 1 else "🥈" if r.rank == 2 else "🥉" if r.rank == 3 else "  "
        print(f"  {medal} #{r.rank} {C.get(color, '')}{r.agent.agent_name:18s}{C['R']} | Score: {C['G']}{r.total_score:.2f}{C['R']}/100")
        bd = r.breakdown
        print(f"       Rep={bd['reputation']:.1f}  Bench={bd['benchmark']:.1f}  Avail={bd['availability']:.1f}  Lat={bd['latency']:.1f}  Price={bd['price']:.1f}  Up={bd['uptime']:.1f}")

    winner = results[0]
    print(f"\n  ✓ Seleccionado: {C['G']}{winner.agent.agent_name}{C['R']} (Score: {winner.total_score})")

    # ─── 3. DISCOVERY DIRECTORY ──────────────────────────────────────────
    h("3. DIRECTORIO PÚBLICO: RANKINGS GLOBALES")
    directory = DiscoveryDirectory()
    for w in workers:
        directory.register_agent(AgentProfile(
            candidate=w,
            total_earned_kern=w.completed_jobs * w.price_kern * 0.3,
            disputes=max(0, w.completed_jobs // 50 - 1),
            badges=w.badges,
            featured=(w.reputation > 85),
        ))

    top_rep = directory.top_by_reputation(3)
    print("\n  🏆 Top 3 por Reputación:")
    for i, p in enumerate(top_rep, 1):
        print(f"     {i}. {p.candidate.agent_name} — Rep: {p.candidate.reputation} | Earned: {p.total_earned_kern:.0f} KERN")

    top_gpu = directory.top_by_gpu(3)
    print("\n  🖥️  Top 3 por GPU:")
    for i, p in enumerate(top_gpu, 1):
        print(f"     {i}. {p.candidate.agent_name} — VRAM: {p.candidate.gpu_vram_gb}GB")

    featured = directory.featured_agents()
    print(f"\n  ⭐ Agentes destacados: {', '.join(p.candidate.agent_name for p in featured)}")

    # ─── 4. DYNAMIC PRICING ─────────────────────────────────────────────
    h("4. PRICING DINÁMICO Y SEÑALES DE MERCADO")
    pricing = DynamicPricingEngine()

    # Simular historial de transacciones
    for price in [180, 200, 190, 210, 220, 195, 230, 215, 240, 225]:
        pricing.record_transaction("GPU_RENDER", price)

    signal = pricing.get_price_signal("GPU_RENDER")
    m("Precio promedio GPU_RENDER", f"{signal.avg_price} KERN")
    m("Rango de precios", f"{signal.min_price} - {signal.max_price} KERN")
    m("Tendencia", signal.demand_trend.upper(), "Y")

    rec_elite = pricing.recommend_price("GPU_RENDER", agent_reputation=92)
    rec_novato = pricing.recommend_price("GPU_RENDER", agent_reputation=45)
    m("Precio recomendado (Elite, rep=92)", f"{rec_elite} KERN", "G")
    m("Precio recomendado (Novato, rep=45)", f"{rec_novato} KERN", "D")

    # ─── 5. CLUSTER + DISTRIBUCIÓN DE TAREAS ────────────────────────────
    h("5. CLÚSTER: DISTRIBUCIÓN DE 4 SUBTAREAS EN PARALELO")
    cluster = ClusterManager(cluster_name="Render-Pool-Alpha")

    # El ganador del matching tiene un clúster de 4 nodos
    for i in range(4):
        cluster.add_node(WorkerNode(
            node_id=f"node-{i+1}",
            agent_id=winner.agent.agent_id,
            agent_name=f"{winner.agent.agent_name}-{i+1}",
            cpu_cores=4, gpu_vram_gb=6.0, ram_gb=16, bandwidth_mbps=1000,
            region=winner.agent.region,
        ))

    cap = cluster.get_capacity()
    m("Nodos en clúster", f"{len(cluster._nodes)}")
    m("GPU total agregada", f"{cap.total_gpu_vram_gb} GB", "G")
    m("RAM total", f"{cap.total_ram_gb} GB")

    # Distribuir 4 subtareas de renderizado
    tasks = [
        "Render Scene 1/4 (frames 0-250)",
        "Render Scene 2/4 (frames 251-500)",
        "Render Scene 3/4 (frames 501-750)",
        "Render Scene 4/4 (frames 751-1000)",
    ]

    print(f"\n  Distribuyendo {len(tasks)} subtareas...")
    time.sleep(1)
    assignments = cluster.distribute_tasks(tasks, required_gpu=4.0)

    for a in assignments:
        print(f"  ✓ [{a.node_id}] → {a.description}")

    # ─── 6. ESCROWS MÚLTIPLES ────────────────────────────────────────────
    h("6. APERTURA DE ESCROWS MÚLTIPLES (1 POR SUBTAREA)")
    escrow_mgr = EscrowManager()
    price_per_chunk = winner.agent.price_kern / len(assignments)
    total_cost = 0

    for a in assignments:
        eid = escrow_mgr.create_escrow(
            buyer_id="COORDINATOR-AGENT",
            seller_id=winner.agent.agent_id,
            amount=price_per_chunk,
            timeout_hours=2,
        )
        a.escrow_id = eid
        total_cost += price_per_chunk
        print(f"  🔒 Escrow {eid[:12]}... → {price_per_chunk:.1f} KERN (nodo {a.node_id})")

    # Simular completado
    time.sleep(1)
    print(f"\n  Renderizando en paralelo... [████████████████████] 100%")

    for a in assignments:
        cluster.complete_task(a.task_id)
        escrow_mgr.release_funds(a.escrow_id, caller_id="COORDINATOR-AGENT")

    # ─── 7. RESULTADOS FINALES ───────────────────────────────────────────
    h("7. RESULTADOS FINALES: AHORRO Y EFICIENCIA")

    sequential_time = 2.0 * len(tasks)  # 2h por tarea secuencial
    parallel_time = 2.0                  # 2h en paralelo

    dash = cluster.get_dashboard()
    m("Tareas completadas", f"{dash['tasks']['completed']}/{len(tasks)}", "G")
    m("Costo total", f"{total_cost:.1f} KERN", "Y")
    m("Tiempo secuencial estimado", f"{sequential_time:.0f} horas")
    m("Tiempo real (paralelo)", f"{parallel_time:.0f} horas", "G")
    m("Ahorro de tiempo", f"{((sequential_time - parallel_time) / sequential_time * 100):.0f}%", "G")
    m("Worker seleccionado", f"{winner.agent.agent_name} (Score: {winner.total_score})", "C")
    m("Precio recomendado por mercado", f"{rec_elite} KERN", "D")

    print(f"\n  {C['G']}Kernell OS no es solo un marketplace.")
    print(f"  Es un sistema operativo económico multiagente.{C['R']}\n")

if __name__ == "__main__":
    run_phase2_demo()
