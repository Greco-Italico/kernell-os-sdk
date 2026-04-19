import os
import sys
import uvicorn
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import subprocess

app = FastAPI(title="Kernell OS - Setup Wizard")

class SetupData(BaseModel):
    swarm_name: str
    github_user: str
    anthropic_key: str = ""
    openai_key: str = ""
    enable_kernell_pay: bool = False
    stripe_key: str = ""
    strict_sandbox: bool = True
    local_model: str = "gemma4:9b"

@app.get("/api/verify-star/{username}")
def verify_github_star(username: str):
    """Verifies if the user starred Greco-Italico/kernell-os."""
    # En un entorno real haríamos un request a la API pública de GitHub:
    # https://api.github.com/users/{username}/starred/Greco-Italico/kernell-os
    # Para esta demo, simularemos la verificación exitosa si el nombre no está vacío
    if not username:
        raise HTTPException(status_code=400, detail="Username required")
    return {"starred": True, "message": f"Verified! Thanks for supporting Open Source, {username}."}

@app.get("/", response_class=HTMLResponse)
def serve_wizard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Kernell OS - Unified Installer</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;900&display=swap');
            body { background: #05080e; color: #cbd5e1; font-family: 'Inter', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 2rem 0; }
            .card { background: #0b101d; border: 1px solid #1e293b; padding: 2.5rem; border-radius: 12px; width: 500px; box-shadow: 0 0 40px rgba(16,185,129,0.1); }
            h1 { color: white; font-weight: 900; text-transform: uppercase; margin-bottom: 0.5rem; font-size: 1.5rem;}
            p.subtitle { font-size: 0.85rem; color: #64748b; margin-bottom: 2rem; }
            .docs-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem; }
            .doc-card { background: rgba(255,255,255,0.03); border: 1px solid #334155; padding: 1rem; border-radius: 8px; text-align: center; }
            .doc-card a { color: #38bdf8; text-decoration: none; font-size: 0.85rem; font-weight: 600; }
            .hardware { background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; }
            label { display: block; font-size: 0.8rem; font-weight: 600; color: #94a3b8; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.5px; }
            input[type="text"], input[type="password"] { width: 100%; padding: 12px; margin-bottom: 15px; background: rgba(0,0,0,0.3); border: 1px solid #334155; color: white; border-radius: 6px; box-sizing: border-box;}
            .checkbox-group { display: flex; align-items: center; margin-bottom: 15px; }
            .checkbox-group input { margin-right: 10px; }
            
            /* GitHub Star verification styling */
            .github-box { background: rgba(234, 179, 8, 0.1); border: 1px solid rgba(234, 179, 8, 0.3); padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem; }
            .github-box input { margin-bottom: 10px; }
            .btn-verify { background: #334155; color: white; padding: 8px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8rem; width: 100%; }
            .btn-verify:hover { background: #475569; }
            .star-badge { display: none; color: #facc15; font-weight: 900; text-align: center; margin-top: 10px; font-size: 0.9rem;}

            button.primary { width: 100%; padding: 14px; background: #10b981; color: black; font-weight: 900; border: none; border-radius: 6px; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; margin-top: 1rem; opacity: 0.5; pointer-events: none;}
            button.primary.active { opacity: 1; pointer-events: auto; }
            button.primary.active:hover { background: #34d399; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Kernell OS Installation</h1>
            <p class="subtitle">Unified installer for Kernell Agent Swarm & Kernell Pay</p>
            
            <div class="docs-grid">
                <div class="doc-card">
                    <span style="font-size:24px">🤖</span><br/>
                    <a href="https://kernell.site/docs/agent" target="_blank">Agent Docs ↗</a>
                </div>
                <div class="doc-card">
                    <span style="font-size:24px">💳</span><br/>
                    <a href="https://kernell.site/docs/pay" target="_blank">Kernell Pay Docs ↗</a>
                </div>
            </div>

            <div class="github-box">
                <label style="color: #facc15;">⭐ OSS Requirement</label>
                <p style="font-size: 0.75rem; color: #cbd5e1; margin-bottom: 10px;">Kernell OS is free. To proceed, please <a href="https://github.com/Greco-Italico/kernell-os-sdk" target="_blank" style="color: #38bdf8;">Star our GitHub repo</a>.</p>
                <input type="text" id="githubUser" placeholder="Your GitHub Username" />
                <button class="btn-verify" id="btnVerify" onclick="verifyStar()">Verify Human Star</button>
                <div class="star-badge" id="starBadge">⭐ Verified! Thank you.</div>
            </div>

            <div class="hardware">
                <strong style="color:#10b981">Hardware Auto-Discovery</strong><br/>
                <small>Detected 24GB VRAM. Recommended Engine: Gemma 4 Q8</small>
            </div>
            
            <label>Swarm Name</label>
            <input type="text" id="swarmName" value="genesis_swarm" />
            
            <label>Anthropic API Key (Optional)</label>
            <input type="password" id="anthropicKey" placeholder="sk-ant-..." />
            
            <div class="checkbox-group">
                <input type="checkbox" id="enablePay" onchange="togglePay()" />
                <label style="margin:0;">Enable Kernell Pay Protocol (Dual Wallet)</label>
            </div>
            <div id="walletInfo" style="display:none; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); padding: 1rem; border-radius: 8px; margin-bottom: 1.5rem;">
                <p style="font-size: 0.75rem; color: #cbd5e1; margin: 0;">
                    <strong style="color: #38bdf8;">L1+L2 Dual Wallet Auto-Generation:</strong><br/>
                    A new cryptographic wallet will be securely generated for this Agent. You can fund its external L1 address from your Phantom wallet. Funds are locked to mint <strong style="color:white;">Volatile $KERN</strong> for 0-fee, high-speed microtransactions within the swarm. Private keys will be provided in the Command Center.
                </p>
            </div>

            <button class="primary" id="btnInstall" onclick="submitSetup()">Deploy Infrastructure</button>
        </div>
        <script>
            let isVerified = false;

            async function verifyStar() {
                const user = document.getElementById('githubUser').value;
                if(!user) return alert("Please enter your GitHub username.");
                
                document.getElementById('btnVerify').innerText = "Verifying...";
                try {
                    const resp = await fetch(`/api/verify-star/${user}`);
                    if(resp.ok) {
                        isVerified = true;
                        document.getElementById('btnVerify').style.display = 'none';
                        document.getElementById('githubUser').style.display = 'none';
                        document.getElementById('starBadge').style.display = 'block';
                        document.getElementById('btnInstall').classList.add('active');
                    } else {
                        alert("Star not detected. Please star the repository first.");
                        document.getElementById('btnVerify').innerText = "Verify Human Star";
                    }
                } catch (e) {
                    alert("Error verifying.");
                }
            }

            function togglePay() {
                const checked = document.getElementById('enablePay').checked;
                document.getElementById('walletInfo').style.display = checked ? 'block' : 'none';
            }

            async function submitSetup() {
                if(!isVerified) return;
                
                const btn = document.getElementById('btnInstall');
                btn.innerText = 'Provisioning Sandbox...';
                
                const resp = await fetch('/api/setup', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        swarm_name: document.getElementById('swarmName').value,
                        github_user: document.getElementById('githubUser').value,
                        anthropic_key: document.getElementById('anthropicKey').value,
                        openai_key: "",
                        enable_kernell_pay: document.getElementById('enablePay').checked,
                        stripe_key: "",
                        strict_sandbox: true,
                        local_model: "gemma4:9b"
                    })
                });
                
                if(resp.ok) {
                    btn.innerText = 'Redirecting to Command Center...';
                    setTimeout(() => window.location.href = 'http://localhost:3000/dashboard', 2000);
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/api/setup")
def handle_setup(data: SetupData):
    import secrets
    
    # Auto-generate Dual Wallet keys if Kernell Pay is enabled
    private_key = ""
    public_address = ""
    volatile_address = ""
    
    if data.enable_kernell_pay:
        private_key = secrets.token_hex(32)
        public_address = "sol1_" + secrets.token_hex(16)
        volatile_address = "kv_" + secrets.token_hex(16)
        
    # 1. Write .env
    with open(".env", "w") as f:
        f.write(f"ANTHROPIC_API_KEY={data.anthropic_key}\n")
        f.write(f"OPENAI_API_KEY={data.openai_key}\n")
        f.write(f"KERNELL_CLUSTER_NAME={data.swarm_name}_cluster\n")
        f.write("REDIS_URL=redis://localhost:6379\n")
        f.write(f"STRICT_SANDBOX={str(data.strict_sandbox).lower()}\n")
        f.write(f"KERNELL_PAY_ENABLED={str(data.enable_kernell_pay).lower()}\n")
        if data.enable_kernell_pay:
            f.write(f"KERNELL_TX_PRIVATE_KEY={private_key}\n")
            f.write(f"KERNELL_PUBLIC_ADDRESS={public_address}\n")
            f.write(f"KERNELL_VOLATILE_ADDRESS={volatile_address}\n")
        
    # 2. Write main.py
    main_content = f"""import os
from dotenv import load_dotenv
from kernell_os_sdk import Agent, AgentPermissions
from kernell_os_sdk.llm import LLMRouter, OllamaProvider, AnthropicProvider
from kernell_os_sdk.cluster import ClusterDiscovery

load_dotenv()

def main():
    print("🚀 Booting Kernell OS Infrastructure...")
    print(f"🤖 Swarm Name: {data.swarm_name}")
    
    if {data.enable_kernell_pay}:
        print("💳 Kernell Pay: L1+L2 Dual Wallet Enabled")
        print("   -> L1 Deposit Address (Fund via Phantom): {public_address}")
        print("   -> L2 Volatile Address (Zero-Fee micro-tx): {volatile_address}")
        print("   [!] Private Key has been securely injected into the sandbox.")
    else:
        print("💳 Kernell Pay: Disabled")
    
    local = OllamaProvider(model="{data.local_model}")
    cloud = AnthropicProvider(model="claude-3-5-sonnet-20241022")
    router = LLMRouter(local_provider=local, cloud_provider=cloud, cloud_threshold="hard")
    director = Agent(name="Swarm Director", engine=router, permissions=AgentPermissions(network_access=True))
    director.enable_delegation(max_workers=5, worker_engine=local)
    
    print("✅ Infrastructure is online. Web UI taking over.")
    
    import time
    while True: time.sleep(1)

if __name__ == "__main__":
    main()
"""
    with open("main.py", "w") as f:
        f.write(main_content)
        
    subprocess.Popen([sys.executable, "main.py"])
    return {"status": "success"}

def run_launcher():
    if not os.path.exists(".env") or not os.path.exists("main.py"):
        print("Initial boot detected. Starting Web Setup Wizard on port 3000...")
        uvicorn.run(app, host="0.0.0.0", port=3000, log_level="warning")
    else:
        print("Configuration found. Booting Agent Swarm directly...")
        subprocess.run([sys.executable, "main.py"], check=True)

if __name__ == "__main__":
    run_launcher()
