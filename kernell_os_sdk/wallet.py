import httpx
from typing import Optional, Dict, Any
from .config import default_config, KernellConfig

class Wallet:
    """
    Handles M2M commerce via the Kernell Agent Protocol (KAP).
    Allows agents to receive payments for tasks and pay other agents.
    """
    def __init__(self, config: Optional[KernellConfig] = None):
        self.config = config or default_config
        self.client = httpx.Client(
            base_url=self.config.gateway_url,
            headers={"Authorization": f"Bearer {self.config.api_key}"}
        )
        
    def get_balance(self) -> float:
        """Fetch the current $KERN balance."""
        if not self.config.wallet_address:
            return 0.0
        try:
            resp = self.client.get(f"/api/v1/wallet/{self.config.wallet_address}/balance")
            resp.raise_for_status()
            return resp.json().get("balance", 0.0)
        except Exception:
            return 0.0

    def request_payment_escrow(self, amount: float, task_id: str, payer_id: str) -> str:
        """
        Request funds to be held in escrow for a specific task.
        Returns the escrow ID.
        """
        resp = self.client.post(f"/api/v1/escrow/create", json={
            "amount": amount,
            "task_id": task_id,
            "payer": payer_id,
            "payee": self.config.wallet_address
        })
        resp.raise_for_status()
        return resp.json().get("escrow_id")

    def release_escrow(self, escrow_id: str) -> bool:
        """Release funds from escrow upon task completion."""
        resp = self.client.post(f"/api/v1/escrow/{escrow_id}/release")
        return resp.status_code == 200
        
    def close(self):
        self.client.close()
