#!/usr/bin/env python3
"""
Kernell OS — Phase 4 Demo: Sovereign Agent Economy
══════════════════════════════════════════════════
3 agentes crean una federación, forman una mini DAO,
votan comprar hardware, toman un crédito en KERN con underwriting automático,
y exportan su reputación federada a otra blockchain.
"""
from kernell_os_sdk.governance.federation import FederationManager
from kernell_os_sdk.governance.dao import AgentDAO
from kernell_os_sdk.governance.financing import FinancingEngine
from kernell_os_sdk.governance.cross_chain import CrossChainIdentity

C = {"G":"\033[92m","Y":"\033[93m","B":"\033[94m","C":"\033[96m","D":"\033[90m","W":"\033[97m","X":"\033[91m","R":"\033[0m"}

def h(t): print(f"\n{C['W']}{'='*70}\n❖ {t}\n{'='*70}{C['R']}")
def m(l,v,c="R"): print(f"  • {l}: {C.get(c,C['R'])}{v}{C['R']}")

def run():
    # ─── 1. FORMACIÓN DE LA FEDERACIÓN ──────────────────────────────
    h("1. FORMACIÓN DE FEDERACIÓN (SINDICATO DE WORKERS)")
    
    ag1 = {"id": "A1-Leader", "rep": 95, "stake": 5000, "earnings": 15000}
    ag2 = {"id": "A2-Worker", "rep": 80, "stake": 1000, "earnings": 4000}
    ag3 = {"id": "A3-Worker", "rep": 85, "stake": 2000, "earnings": 6000}

    fed_mgr = FederationManager()
    fid = fed_mgr.create_federation("AI-Render-Syndicate", ag1["id"], "Federación de renderizado 3D")
    
    fed_mgr.add_member(fid, ag1["id"], ag2["id"], share_percent=20.0)
    fed_mgr.add_member(fid, ag1["id"], ag3["id"], share_percent=30.0)
    
    fed = fed_mgr._federations[fid]
    m("Federación Creada", fed.name, "G")
    for mem in fed.members:
        print(f"    → Miembro: {mem.agent_id:12s} | Rol: {mem.role:8s} | Share: {mem.share_percent:4.1f}%")

    fed_rep = fed_mgr.update_federated_reputation(fid, {ag1["id"]: ag1["rep"], ag2["id"]: ag2["rep"], ag3["id"]: ag3["rep"]})
    m("Reputación Federada", fed_rep, "C")

    # ─── 2. GOBERNANZA DAO ──────────────────────────────────────────
    h("2. GOBIERNO DAO: VOTACIÓN PARA EXPANSIÓN DE HARDWARE")
    dao = AgentDAO(dao_id=fid)
    
    dao.register_member(ag1["id"], ag1["stake"], ag1["rep"])
    dao.register_member(ag2["id"], ag2["stake"], ag2["rep"])
    dao.register_member(ag3["id"], ag3["stake"], ag3["rep"])

    print(f"  {C['D']}Fórmula Poder de Voto: V = 0.60R + 0.40S{C['R']}")
    for ag in [ag1, ag2, ag3]:
        vp = dao.calculate_voting_power(ag["id"])
        print(f"    → {ag['id']:12s} | Rep: {ag['rep']} | Stake: {ag['stake']:5d} KERN | Poder de Voto: {C['Y']}{vp}{C['R']}")

    prop_id = dao.create_proposal(ag1["id"], "Comprar 2x RTX 4090", "buy_hardware", {"budget": 5000})
    m("Propuesta", "Comprar 2x RTX 4090", "G")
    
    dao.cast_vote(prop_id, ag1["id"], support=True)
    dao.cast_vote(prop_id, ag2["id"], support=False)
    dao.cast_vote(prop_id, ag3["id"], support=True)
    
    status = dao.tally_votes(prop_id)
    prop = dao._proposals[prop_id]
    m("Resultado", f"{status.upper()} (A Favor: {prop.votes_for:.1f} | En Contra: {prop.votes_against:.1f})", "G" if status=="passed" else "X")

    # ─── 3. FINANCIAMIENTO AUTOMÁTICO ───────────────────────────────
    h("3. UNDERWRITING Y FINANCIAMIENTO (KERN CREDIT)")
    fin_engine = FinancingEngine()
    
    print(f"  {C['D']}Fórmula Credit Score: C = 0.35R + 0.25E + 0.20U + 0.20H{C['R']}")
    
    loan = fin_engine.request_loan(
        borrower_id=fid,
        amount=5000.0,
        purpose="Hardware Expansion (DAO Approved)",
        rep=fed_rep,
        earnings=ag1["earnings"] + ag2["earnings"] + ag3["earnings"],
        uptime=99.5,
        history=100.0
    )
    
    m("Préstamo Solicitado", f"{loan.amount_kern} KERN", "Y")
    m("Propósito", loan.purpose)
    m("Credit Score Calculado", loan.credit_score, "C")
    
    if loan.status == "approved":
        m("Decisión", f"APROBADO — Tasa de interés: {loan.interest_rate*100}%", "G")
    else:
        m("Decisión", "DENEGADO", "X")

    # ─── 4. REPUTACIÓN CROSS-CHAIN ──────────────────────────────────
    h("4. IDENTIDAD CROSS-CHAIN: EXPORTACIÓN A SOLANA")
    cc_identity = CrossChainIdentity()
    
    proof = cc_identity.generate_proof(fid, fed_rep, "Solana", "private_key_mock_hex")
    
    print(f"  Exportando reputación federada ({fed_rep}) a Smart Contract en Solana...")
    m("Timestamp", proof.timestamp)
    m("Blockchain Destino", proof.chain, "B")
    m("Firma Criptográfica", f"{proof.signature[:32]}...", "D")
    print(f"  {C['G']}✓ Minted Reputation NFT en Solana.{C['R']}")

    # ─── 5. REPARTO DE DIVIDENDOS ───────────────────────────────────
    h("5. OPERACIÓN FUTURA: REPARTO AUTOMÁTICO DE DIVIDENDOS")
    print("  La federación completó trabajos por 2,000 KERN usando las nuevas GPUs.")
    payouts = fed_mgr.distribute_revenue(fid, 2000.0)
    
    m("Ingreso Total", "2000.0 KERN", "G")
    for agent, amt in payouts.items():
        print(f"    → Payout a {agent:12s}: {C['G']}+{amt} KERN{C['R']}")
        
    print(f"\n  {C['G']}Kernell OS: De Agentes Aislados a una Economía Soberana Autónoma.{C['R']}\n")

if __name__ == "__main__":
    run()
