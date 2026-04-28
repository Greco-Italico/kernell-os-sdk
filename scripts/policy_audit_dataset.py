#!/usr/bin/env python3
"""
Audit labeled policy dataset and produce structured sampling for manual review.

Output:
- global distribution report
- sampled review set:
  - 10 premium_overkill
  - 10 underestimation
  - 10 misroute
  - 20 random
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List


def _read_jsonl(path: Path) -> List[dict]:
    rows: List[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _avg(values: List[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def _sample(rows: List[dict], n: int, rng: random.Random) -> List[dict]:
    if len(rows) <= n:
        return list(rows)
    return rng.sample(rows, n)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit labeled policy dataset")
    parser.add_argument("--input", required=True, help="Path to labeled.jsonl")
    parser.add_argument("--report-output", default="", help="Optional report JSON output path")
    parser.add_argument("--sample-output", default="", help="Optional sampled JSONL output path")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = _read_jsonl(Path(args.input))
    rng = random.Random(args.seed)

    route_counts = Counter(r.get("optimal_route", "unknown") for r in rows)
    error_counts = Counter(r.get("error_type", "unknown") for r in rows)

    cost_by_route: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        cost_by_route[r.get("optimal_route", "unknown")].append(float(r.get("cost_usd", 0.0)))

    downgrade_cases = [
        r for r in rows
        if r.get("actual_route") == "premium" and r.get("optimal_route") in ("cheap", "local")
    ]

    premium_overkill = [r for r in rows if "premium_overkill" in str(r.get("label_reason", ""))]
    underestimation = [r for r in rows if r.get("error_type") == "underestimation"]
    misroute = [r for r in rows if r.get("error_type") == "misroute"]

    sampled = (
        _sample(premium_overkill, 10, rng)
        + _sample(underestimation, 10, rng)
        + _sample(misroute, 10, rng)
        + _sample(rows, 20, rng)
    )

    report = {
        "total_rows": len(rows),
        "route_distribution": dict(route_counts),
        "error_types": dict(error_counts),
        "avg_cost_by_route": {k: round(_avg(v), 6) for k, v in cost_by_route.items()},
        "downgrade_cases": len(downgrade_cases),
        "review_sample_size": len(sampled),
        "review_buckets": {
            "premium_overkill_pool": len(premium_overkill),
            "underestimation_pool": len(underestimation),
            "misroute_pool": len(misroute),
        },
    }

    print(json.dumps(report, indent=2))

    if args.report_output:
        out = Path(args.report_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2))

    if args.sample_output:
        out = Path(args.sample_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w") as f:
            for row in sampled:
                f.write(json.dumps(row) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
