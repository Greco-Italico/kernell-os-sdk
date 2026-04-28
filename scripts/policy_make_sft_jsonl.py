#!/usr/bin/env python3
"""
Convert labeled policy dataset into SFT JSONL format.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _to_sft(example: dict) -> dict:
    prompt = (
        "Task metadata:\n"
        f"- domain: {example.get('task_domain', 'general')}\n"
        f"- tokens: {example.get('task_token_count', 0)}\n"
        f"- hardware: {example.get('hardware_tier', '')}\n"
        f"- has_gpu: {example.get('has_gpu', False)}\n"
        f"- predicted_route: {example.get('predicted_route', '')}\n"
        f"- was_escalated: {example.get('was_escalated', False)}\n"
        f"- success: {example.get('success', False)}\n"
        f"- observed_cost: {example.get('cost_usd', 0.0)}\n"
        f"- observed_latency_s: {example.get('latency_s', 0.0)}\n\n"
        "Return the optimal policy decision JSON."
    )
    completion = {
        "route": example.get("optimal_route", "cheap"),
        "confidence": float(example.get("label_confidence", 0.7)),
        "needs_decomposition": example.get("optimal_route", "cheap") == "hybrid",
        "risk": "high" if example.get("should_use_premium", False) else "medium",
        "expected_cost_usd": float(example.get("cost_usd", 0.0)),
        "expected_latency_s": float(example.get("latency_s", 0.0)),
        "max_budget_usd": float(example.get("cost_usd", 0.0)) * 1.2,
    }
    return {"prompt": prompt, "completion": json.dumps(completion)}


def main() -> int:
    p = argparse.ArgumentParser(description="Build SFT JSONL from labeled policy dataset")
    p.add_argument("--input", required=True, help="Labeled JSONL input")
    p.add_argument("--output", required=True, help="SFT JSONL output")
    args = p.parse_args()

    records = [_to_sft(x) for x in _read_jsonl(Path(args.input))]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    print(f"wrote {len(records)} records to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
