#!/usr/bin/env python3
"""
Kernell OS — Phase 3 Demo: GPU Market + Clusters + Auctions + Insurance
═══════════════════════════════════════════════════════════════════════
Un agente necesita renderizar una película. El sistema:
1. Busca GPUs en el mercado
2. Lanza subasta entre candidatos
3. Distribuye entre 10 nodos
4. Simula fallo y failover automático
5. Activa seguro de ejecución
6. Muestra ahorro final
"""
import time
from kernell_os_sdk.marketplace.gpu_market import GPUMarketplace, GPUListing, GPUModel
from kernell_os_sdk.marketplace.auction import LiveAuctionEngine, AuctionBid
from kernell_os_sdk.cluster.compute_pool import ResilientComputePool, PoolPolicy, WorkerNode
from kernell_os_sdk.marketplace.insurance import ExecutionInsurance, RiskLevel
from kernell_os_sdk.escrow.manager import EscrowManager

C = {"G":"\033[92m","Y":"\033[93m","B":"\033[94m","C":"\033[96m","D":"\033[90m","W":"\033[97m","X":"\033[91m","R":"\033[0m"}

def h(t):
    print(f"\n{C['W']}{'='*70}\n❖ {t}\n{'='*70}{C['R']}")

def m(l,v,c="R"):
    print(f"  • {l}: {C.get(c,C['R'])}{v}{C['R']}")

def run():
    # ─── 1. GPU MARKETPLACE ──────────────────────────────────────────
    h("1. MERCADO DE GPUs: INVENTARIO DISPONIBLE")
    gpu_market = GPUMarketplace()

    gpus = [
        GPUListing(owner_agent_id="A1", owner_name="Atlas-GPU",    gpu_model=GPUModel.RTX_4090, vram_gb=24, cuda_cores=16384, benchmark_score=82, reputation=92, region="US-East", price_per_hour_kern=25),
        GPUListing(owner_agent_id="A2", owner_name="Nebula-H100",  gpu_model=GPUModel.H100,     vram_gb=80, cuda_cores=16896, benchmark_score=100,reputation=95, region="US-East", price_per_hour_kern=60),
        GPUListing(owner_agent_id="A3", owner_name="Budget-T4",    gpu_model=GPUModel.T4,       vram_gb=16, cuda_cores=2560,  benchmark_score=40, reputation=70, region="LATAM",   price_per_hour_kern=8),
        GPUListing(owner_agent_id="A4", owner_name="Euro-A100",    gpu_model=GPUModel.A100,     vram_gb=80, cuda_cores=6912,  benchmark_score=90, reputation=88, region="EU-West", price_per_hour_kern=45),
        GPUListing(owner_agent_id="A5", owner_name="Fast-4080",    gpu_model=GPUModel.RTX_4080, vram_gb=16, cuda_cores=9728,  benchmark_score=70, reputation=80, region="US-East", price_per_hour_kern=18),
    ]
    for g in gpus:
        gpu_market.list_gpu(g)
        print(f"  {C['C']}[{g.gpu_model.value:10s}]{C['R']} {g.owner_name:16s} | VRAM:{g.vram_gb:3.0f}GB | {g.price_per_hour_kern:5.1f} KERN/h | Rep:{g.reputation} | {g.region}")

    # Búsqueda filtrada
    print(f"\n  {C['D']}Búsqueda: VRAM≥24GB, región=US-East, job=render{C['R']}")
    results = gpu_market.search(min_vram=24, region="US-East", job_type="render", sort_by="benchmark")
    for r in results:
        print(f"  → {C['G']}{r.owner_name}{C['R']} ({r.gpu_model.value}) — {r.price_per_hour_kern} KERN/h")

    # ─── 2. SUBASTA EN VIVO ──────────────────────────────────────────
    h("2. SUBASTA EN VIVO: RENDERIZADO DE PELÍCULA (10 ESCENAS)")
    auction_engine = LiveAuctionEngine()
    aid = auction_engine.create_auction(
        creator_id="DIRECTOR-BOT",
        title="Render 4K Movie — 10 scenes",
        category="GPU_RENDER",
        max_budget=500.0,
        min_bid=50.0,
        sla_hours=4,
        min_reputation=60.0,
        duration_minutes=5,
    )

    bids = [
        AuctionBid(bidder_id="A1", bidder_name="Atlas-GPU",   price_kern=200, delivery_hours=2, reputation=92, availability=90),
        AuctionBid(bidder_id="A2", bidder_name="Nebula-H100", price_kern=350, delivery_hours=1, reputation=95, availability=95),
        AuctionBid(bidder_id="A4", bidder_name="Euro-A100",   price_kern=280, delivery_hours=2, reputation=88, availability=85),
        AuctionBid(bidder_id="A5", bidder_name="Fast-4080",   price_kern=150, delivery_hours=4, reputation=80, availability=100),
    ]
    for b in bids:
        auction_engine.place_bid(aid, b)
        print(f"  📩 Puja: {b.bidder_name:16s} | {b.price_kern:6.0f} KERN | {b.delivery_hours}h | Rep:{b.reputation}")

    winner = auction_engine.close_and_select_winner(aid)
    board = auction_engine.get_auction_board(aid)

    print(f"\n  {C['D']}Fórmula: S = 0.35P + 0.25R + 0.20SLA + 0.20A{C['R']}")
    print(f"\n  Ranking final de pujas:")
    auction = auction_engine._auctions[aid]
    for i, b in enumerate(auction.bids, 1):
        medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "  "
        print(f"  {medal} #{i} {b.bidder_name:16s} | Score: {C['G']}{b.score:.2f}{C['R']} | {b.price_kern} KERN")

    m("Ganador", f"{winner.bidder_name} (Score: {winner.score})", "G")

    # ─── 3. CLÚSTER RESILIENTE ───────────────────────────────────────
    h("3. DISTRIBUCIÓN EN CLÚSTER RESILIENTE (10 NODOS, 2 FALLOS)")
    pool = ResilientComputePool("Render-Farm-Alpha", PoolPolicy(failover_enabled=True, max_retries=3))

    for i in range(12):  # 12 nodos (2 de backup)
        pool.add_node(WorkerNode(
            node_id=f"gpu-{i+1:02d}",
            agent_id=winner.bidder_id,
            agent_name=f"{winner.bidder_name}-{i+1}",
            cpu_cores=4, gpu_vram_gb=24, ram_gb=16,
            bandwidth_mbps=1000, region="US-East",
        ))

    tasks = [f"Render Scene {i+1}/10 (frames {i*100}-{(i+1)*100-1})" for i in range(10)]

    # Simular fallo en escena 3 y 7
    executions = pool.execute_with_resilience(tasks, required_gpu=12.0, simulate_failures=[2, 6])

    cap = pool.cluster.get_capacity()
    m("Nodos totales", f"{len(pool.cluster._nodes)} (incl. 2 backup)")
    m("GPU agregada", f"{cap.total_gpu_vram_gb} GB", "G")

    print(f"\n  Ejecución de tareas:")
    for e in executions:
        status_color = "G" if e.status == "completed" else "X"
        failover_tag = f" {C['Y']}[failover from {e.failover_from}]{C['R']}" if e.failover_from else ""
        print(f"  {'✓' if e.status=='completed' else '✗'} {C.get(status_color,'')}{e.task_description}{C['R']} → {e.assigned_node}{failover_tag}")

    # ─── 4. SEGURO DE EJECUCIÓN ──────────────────────────────────────
    h("4. SEGURO DE EJECUCIÓN ACTIVADO (NODOS CAÍDOS)")
    insurance = ExecutionInsurance()
    escrow_mgr = EscrowManager()

    failed_execs = [e for e in executions if e.failover_from]
    for fe in failed_execs:
        eid = escrow_mgr.create_escrow("DIRECTOR-BOT", winner.bidder_id, 50.0, 4)
        pid = insurance.create_policy(eid, "DIRECTOR-BOT", winner.bidder_id, 50.0, RiskLevel.MEDIUM, backup_id="BACKUP-AGENT")
        claim = insurance.claim(pid)
        m(f"Nodo caído {fe.failover_from}", f"Refund: {claim['refund_to_buyer']} KERN | Penalización: {claim['penalty_to_seller']} KERN | Failover → {fe.assigned_node}", "Y")

    # ─── 5. REPORTE FINAL ────────────────────────────────────────────
    h("5. REPORTE FINAL DE INFRAESTRUCTURA")
    report = pool.get_resilience_report()
    m("Tareas completadas", f"{report['completed']}/{report['total_tasks']}", "G")
    m("Failovers ejecutados", f"{report['failovers_triggered']}", "Y")
    m("Nodos caídos", f"{report['nodes_failed']}", "X")
    m("Tasa de éxito", report['success_rate'], "G")

    seq_time = 10 * 2  # 10 escenas × 2h cada una
    par_time = 2       # 2h en paralelo
    m("Tiempo secuencial", f"{seq_time}h")
    m("Tiempo real (paralelo)", f"{par_time}h", "G")
    m("Ahorro de tiempo", f"{((seq_time-par_time)/seq_time*100):.0f}%", "G")
    m("Costo total", f"{winner.price_kern} KERN", "Y")

    print(f"\n  {C['D']}Event Log:{C['R']}")
    for log in report['event_log'][:8]:
        print(f"    {log}")

    print(f"\n  {C['G']}Kernell OS: mercado de infraestructura autónoma entre agentes.{C['R']}\n")

if __name__ == "__main__":
    run()
