"""Aggregate benchmark JSONL runs into business-facing metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean


def _read_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _avg(rows: list[dict], key: str) -> float:
    return mean(float(r.get(key, 0.0)) for r in rows) if rows else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate Kernell benchmark JSONL")
    parser.add_argument("--run-file", required=True, help="Path to benchmark JSONL run")
    parser.add_argument("--quality-drop-threshold", type=float, default=0.05)
    args = parser.parse_args()

    rows = _read_rows(Path(args.run_file))
    baseline = [r for r in rows if r.get("mode") == "baseline"]
    kernell = [r for r in rows if r.get("mode") == "kernell"]

    baseline_cost = sum(float(r["cost_usd"]) for r in baseline)
    kernell_cost = sum(float(r["cost_usd"]) for r in kernell)
    baseline_latency = _avg(baseline, "latency_s")
    kernell_latency = _avg(kernell, "latency_s")
    baseline_quality = _avg(baseline, "quality_score")
    kernell_quality = _avg(kernell, "quality_score")
    savings_pct = ((baseline_cost - kernell_cost) / baseline_cost * 100.0) if baseline_cost > 0 else 0.0
    latency_delta_pct = ((kernell_latency - baseline_latency) / baseline_latency * 100.0) if baseline_latency > 0 else 0.0
    quality_drop = baseline_quality - kernell_quality

    report = {
        "baseline_cost": round(baseline_cost, 6),
        "kernell_cost": round(kernell_cost, 6),
        "savings_pct": round(savings_pct, 2),
        "latency_baseline": round(baseline_latency, 4),
        "latency_kernell": round(kernell_latency, 4),
        "latency_delta_pct": round(latency_delta_pct, 2),
        "quality_pass_rate_baseline": round(sum(1 for r in baseline if r.get("success")) / max(len(baseline), 1), 4),
        "quality_pass_rate_kernell": round(sum(1 for r in kernell if r.get("success")) / max(len(kernell), 1), 4),
        "quality_score_baseline": round(baseline_quality, 4),
        "quality_score_kernell": round(kernell_quality, 4),
        "quality_drop": round(quality_drop, 4),
        "quality_guardrail_ok": quality_drop <= args.quality_drop_threshold,
        "value_generated_usd_per_1k_tasks": round((baseline_cost - kernell_cost) * 1000.0 / max(len(baseline), 1), 2),
        "run_file": args.run_file,
    }

    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
