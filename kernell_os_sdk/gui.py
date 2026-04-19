"""
Kernell OS SDK — Agent GUI & Control Panel
══════════════════════════════════════════════════════════════
A lightweight local web dashboard for the Agent.
Allows users to toggle permissions, adjust resources, and view
the Passport/Wallet details in a beautiful UI.
"""
import logging
import threading
from typing import Any
from .agent import Agent

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

logger = logging.getLogger("kernell.gui")

class AgentGUI:
    """Local Control Panel for the Kernell Agent."""
    def __init__(self, agent: Agent, port: int = 8500):
        self.agent = agent
        self.port = port
        self.app = FastAPI(title=f"Kernell Control Panel - {self.agent.name}")
        self._setup_routes()

    def _setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        def index():
            # A beautiful Tailwind CSS + Alpine.js local dashboard
            # This avoids heavy node_modules for SDK users
            html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{self.agent.name} - Kernell OS Control Panel</title>
                <script src="https://cdn.tailwindcss.com"></script>
                <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
                <style>
                    body {{ background-color: #020509; color: #e2e8f0; font-family: 'Inter', sans-serif; }}
                    .glass {{ background: rgba(15, 23, 42, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.1); }}
                    .switch {{ position: relative; display: inline-block; width: 44px; height: 24px; }}
                    .switch input {{ opacity: 0; width: 0; height: 0; }}
                    .slider {{ position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #334155; transition: .4s; border-radius: 24px; }}
                    .slider:before {{ position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }}
                    input:checked + .slider {{ background-color: #a855f7; }}
                    input:checked + .slider:before {{ transform: translateX(20px); }}
                </style>
            </head>
            <body class="p-8">
                <div class="max-w-4xl mx-auto" x-data="agentData()">
                    <div class="flex items-center justify-between mb-8">
                        <h1 class="text-3xl font-bold text-white flex items-center gap-3">
                            <span class="text-purple-500">🌌</span> {self.agent.name}
                        </h1>
                        <span class="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide" 
                              :class="status === 'working' ? 'bg-purple-500/20 text-purple-400' : 'bg-green-500/20 text-green-400'"
                              x-text="status"></span>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <!-- Passport & Identity -->
                        <div class="glass rounded-xl p-6">
                            <h2 class="text-xl font-semibold mb-4 text-white">Cryptographic Passport</h2>
                            <div class="space-y-3 text-sm text-slate-300">
                                <p><span class="text-slate-500">ID:</span> {self.agent.id}</p>
                                <p><span class="text-slate-500">KAP Address:</span> {self.agent.passport.kap_address}</p>
                                <p class="break-all"><span class="text-slate-500">Volatile Wallet:</span> <br>{self.agent.passport.kern_volatile_address}</p>
                            </div>
                        </div>

                        <!-- Permissions Toggle -->
                        <div class="glass rounded-xl p-6">
                            <h2 class="text-xl font-semibold mb-4 text-white">Security Boundaries (PC Control)</h2>
                            <div class="space-y-4">
                                <template x-for="(value, key) in permissions" :key="key">
                                    <div class="flex items-center justify-between">
                                        <span class="text-sm font-medium capitalize" x-text="key.replace(/_/g, ' ')"></span>
                                        <label class="switch">
                                            <input type="checkbox" x-model="permissions[key]" @change="togglePermission(key, permissions[key])">
                                            <span class="slider"></span>
                                        </label>
                                    </div>
                                </template>
                            </div>
                        </div>
                    </div>
                </div>

                <script>
                    function agentData() {{
                        return {{
                            status: '{self.agent.state.status}',
                            permissions: {{
                                network_access: {str(self.agent.permissions.network_access).lower()},
                                file_system_read: {str(self.agent.permissions.file_system_read).lower()},
                                file_system_write: {str(self.agent.permissions.file_system_write).lower()},
                                execute_commands: {str(self.agent.permissions.execute_commands).lower()},
                                gui_automation: {str(self.agent.permissions.gui_automation).lower()}
                            }},
                            async togglePermission(key, value) {{
                                await fetch(`/api/permissions/${{key}}`, {{
                                    method: 'POST',
                                    headers: {{'Content-Type': 'application/json'}},
                                    body: JSON.stringify({{state: value}})
                                }});
                            }}
                        }}
                    }}
                </script>
            </body>
            </html>
            """
            return html

        @self.app.post("/api/permissions/{permission}")
        def update_permission(permission: str, data: dict):
            self.agent.toggle_permission(permission, data.get("state", False))
            return {"status": "updated"}

    def start(self):
        """Starts the GUI server in a non-blocking thread."""
        if not HAS_GUI:
            logger.error("FastAPI or Uvicorn not installed. Run: pip install fastapi uvicorn")
            return

        logger.info(f"Starting Agent Control Panel on http://localhost:{self.port}")
        
        def run_server():
            uvicorn.run(self.app, host="127.0.0.1", port=self.port, log_level="error")
            
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        return thread
