from __future__ import annotations
import os
import time
from dataclasses import dataclass

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

@dataclass
class BaselineResult:
    output: str
    latency_s: float
    cost_usd: float
    tokens_in: int
    tokens_out: int
    success: bool

class OpenAIBaseline:
    """
    Baseline real usando OpenAI.
    Modelo recomendado: gpt-4o-mini (barato + rápido).
    """
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if self.api_key and OpenAI is not None:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
        self.model = model

    def run(self, prompt: str) -> BaselineResult:
        if not self.client:
            return BaselineResult(output="mock baseline output", latency_s=1.0, cost_usd=0.01, tokens_in=0, tokens_out=0, success=True)
        start = time.time()
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            latency = time.time() - start
            text = resp.choices[0].message.content or ""
            usage = resp.usage
            tokens_in = getattr(usage, "prompt_tokens", 0)
            tokens_out = getattr(usage, "completion_tokens", 0)
            
            cost = (tokens_in * 0.00000015) + (tokens_out * 0.0000006)
            
            return BaselineResult(
                output=text,
                latency_s=latency,
                cost_usd=cost,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                success=True,
            )
        except Exception as exc:
            return BaselineResult(
                output=str(exc),
                latency_s=time.time() - start,
                cost_usd=0.0,
                tokens_in=0,
                tokens_out=0,
                success=False,
            )
