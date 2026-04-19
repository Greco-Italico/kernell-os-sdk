import os
from typing import Optional
from pydantic import BaseModel, Field

class KernellConfig(BaseModel):
    """Configuration for the Kernell OS SDK."""
    api_key: str = Field(default_factory=lambda: os.getenv("KERNELL_API_KEY", ""))
    gateway_url: str = Field(default_factory=lambda: os.getenv("KERNELL_GATEWAY_URL", "https://api.kernell.site"))
    redis_url: Optional[str] = Field(default_factory=lambda: os.getenv("KERNELL_REDIS_URL", None))
    environment: str = Field(default_factory=lambda: os.getenv("KERNELL_ENV", "development"))
    
    # Wallet / Escrow configuration
    wallet_address: Optional[str] = Field(default_factory=lambda: os.getenv("KERNELL_WALLET_ADDRESS", None))
    wallet_private_key: Optional[str] = Field(default_factory=lambda: os.getenv("KERNELL_WALLET_KEY", None))
    
    # LLM Defaults
    default_model: str = Field(default="claude-3-5-sonnet-20241022")
    fallback_model: str = Field(default="gpt-4o-mini")
    
    class Config:
        env_prefix = "KERNELL_"

# Global default config
default_config = KernellConfig()
