"""
Kernell OS SDK — Configuration
════════════════════════════════
SECURITY:
  - Sensitive fields (api_key, wallet_private_key) are loaded from
    environment variables and NOT serialized by default.
  - wallet_private_key is excluded from JSON/dict serialization.
"""
import os
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class KernellConfig(BaseModel):
    """Configuration for the Kernell OS SDK."""

    model_config = ConfigDict(env_prefix="KERNELL_")

    api_key: str = Field(default_factory=lambda: os.getenv("KERNELL_API_KEY", ""))
    gateway_url: str = Field(default_factory=lambda: os.getenv("KERNELL_GATEWAY_URL", "https://api.kernell.site"))
    
    @field_validator("gateway_url")
    @classmethod
    def validate_gateway_url(cls, v: str) -> str:
        allowed_domains = ["https://api.kernell.site", "http://localhost", "http://127.0.0.1"]
        if not any(v.startswith(domain) for domain in allowed_domains):
            raise ValueError("SSRF Protection: gateway_url must be an approved Kernell domain or localhost.")
        return v
        
    redis_url: Optional[str] = Field(default_factory=lambda: os.getenv("KERNELL_REDIS_URL", None))
    environment: str = Field(default_factory=lambda: os.getenv("KERNELL_ENV", "development"))

    # Wallet / Escrow configuration
    wallet_address: Optional[str] = Field(default_factory=lambda: os.getenv("KERNELL_WALLET_ADDRESS", None))
    # SECURITY: This field is EXCLUDED from serialization
    wallet_private_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("KERNELL_WALLET_KEY", None),
        exclude=True,  # Never serialize this field
    )

    # LLM Defaults
    default_model: str = Field(default="claude-3-5-sonnet-20241022")
    fallback_model: str = Field(default="gpt-4o-mini")

    def model_dump(self, **kwargs):
        """Override to always exclude sensitive fields."""
        kwargs.setdefault("exclude", set())
        if isinstance(kwargs["exclude"], set):
            kwargs["exclude"].add("wallet_private_key")
            kwargs["exclude"].add("api_key")
        return super().model_dump(**kwargs)


# Global default config
default_config = KernellConfig()
