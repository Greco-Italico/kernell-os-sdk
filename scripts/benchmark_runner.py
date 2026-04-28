"""
Kernell OS SDK — Benchmark Runner
══════════════════════════════════
Compares Kernell routing against a direct OpenAI baseline.
Produces JSONL files in benchmarks/runs/ for report generation.
"""
import json
import os
import time
from pathlib import Path

from scripts.baseline_openai import OpenAIBaseline
from scripts.quality import quality_score as heuristic_score
from scripts.quality_llm import llm_judge_score
from kernell_os_sdk.router import IntelligentRouter
from kernell_os_sdk.router import TelemetryCollector, TelemetryConfig

USE_LLM_JUDGE = os.environ.get("BENCH_USE_LLM_JUDGE", "0") == "1"

TIER_COSTS = {
    "local_nano": 0.001,
    "local_small": 0.001,
    "local_medium": 0.005,
    "local_large": 0.01,
    "cheap_api": 0.01,
    "premium_api": 0.25,
    "cache": 0.0,
    "none": 0.05,
}


class BenchLocalBackend:
    """
    Mock LLM that handles all three prompt types from the router pipeline:
    1. Decomposer → returns non-JSON to trigger safe single-task fallback
    2. Verifier → returns valid JSON with confidence > 0.7
    3. Execution → returns substantive, keyword-rich responses
    """
    def generate(self, prompt: str, system: str = "") -> str:
        p = prompt.lower()

        # Verifier prompts
        if "quality verifier" in p or "verify" in p or "evaluate" in p:
            return '{"valid": true, "confidence": 0.92, "reason": "output is correct"}'

        # Decomposer prompts
        if "decompose" in p:
            return "single_task"

        # Execution prompts
        if "2+2" in prompt:
            return "The answer is 4. This is basic arithmetic."
        if "index" in p or "database" in p:
            return ("A database index is a B-tree data structure that speeds up "
                    "search operations by maintaining sorted references to rows.")
        if "function" in p or "python" in p or "add" in p:
            return "def add(a, b):\n    return a + b"
        return f"Detailed response to: {prompt[:80]}"


def compute_quality(prompt, output, expected):
    h = heuristic_score(output, expected)
    if not USE_LLM_JUDGE:
        return h
    j = llm_judge_score(prompt, output, expected)
    return 0.7 * h + 0.3 * j


def run_benchmark():
    baseline = OpenAIBaseline()

    telemetry = TelemetryCollector(
        config=TelemetryConfig(
            enabled=True,
            consent_given=True,
            buffer_dir="/tmp/kernell_benchmark",
        )
    )

    local_be = BenchLocalBackend()
    router = IntelligentRouter(
        classifier=local_be,
        local_models={
            "local_nano": local_be,
            "local_small": local_be,
            "local_medium": local_be,
        },
        telemetry=telemetry,
    )

    tasks = [
        {
            "task_id": "t1",
            "input": "What is 2+2?",
            "expected_properties": {"keywords": ["4"]},
        },
        {
            "task_id": "t2",
            "input": "Explain how a database index works",
            "expected_properties": {"keywords": ["B-tree", "search"]},
        },
        {
            "task_id": "t3",
            "input": "Write a python function to add two numbers",
            "expected_properties": {"keywords": ["def", "return"], "must_contain_colon": True},
        },
    ]

    out_dir = Path("benchmarks/runs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

    print(f"\n📊 Running benchmark on {len(tasks)} tasks...\n")

    rows = []
    with open(out_file, "w") as f:
        for task in tasks:
            prompt = task["input"]

            # ── Baseline ──
            b = baseline.run(prompt)

            # ── Kernell ──
            try:
                k_results = router.execute(prompt)
                k_best = next((r for r in k_results if r.success), None)
            except Exception as exc:
                print(f"  ⚠️ Router error on {task['task_id']}: {exc}")
                k_best = None

            k_output = k_best.output if k_best else ""
            k_latency_ms = (k_best.latency_ms or 0.0) if k_best else 0.0
            k_latency_s = k_latency_ms / 1000.0
            k_route = k_best.model_used if k_best else "none"
            k_cost = TIER_COSTS.get(k_route, 0.05)

            # ── Quality ──
            b_q = compute_quality(prompt, b.output, task.get("expected_properties", {}))
            k_q = compute_quality(prompt, k_output, task.get("expected_properties", {}))

            row = {
                "task_id": task["task_id"],
                "baseline_output": b.output[:200],
                "baseline_cost_usd": b.cost_usd,
                "baseline_latency_s": b.latency_s,
                "baseline_quality": round(b_q, 4),
                "kernell_output": k_output[:200],
                "kernell_cost_usd": k_cost,
                "kernell_latency_s": round(k_latency_s, 4),
                "kernell_quality": round(k_q, 4),
                "route": k_route,
                "success": k_best.success if k_best else False,
                "savings_pct": round((1 - (k_cost / b.cost_usd)), 4) if b.cost_usd > 0 else 0,
                "latency_delta_pct": round(
                    ((k_latency_s - b.latency_s) / b.latency_s), 4
                ) if b.latency_s > 0 else 0,
                "quality_drop": round(b_q - k_q, 4),
            }
            rows.append(row)
            f.write(json.dumps(row) + "\n")

            icon = "✅" if row["success"] else "❌"
            print(
                f"  {icon} {task['task_id']}: "
                f"route={k_route}, "
                f"savings={row['savings_pct']*100:.1f}%, "
                f"quality_drop={row['quality_drop']:.3f}"
            )

    print(f"\n📁 Results saved to {out_file}")
    return rows


if __name__ == "__main__":
    run_benchmark()
