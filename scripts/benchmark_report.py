"""
Kernell OS SDK — Benchmark Report Generator
════════════════════════════════════════════
Reads the latest benchmark run and prints a summary.
Optionally updates the leaderboard.
"""
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def summarize(rows):
    if not rows:
        return {
            "savings_pct": 0,
            "latency_delta_pct": 0,
            "quality_drop_avg": 0,
            "quality_guardrail_ok": False,
            "success_rate": 0,
        }

    savings = [r["savings_pct"] for r in rows]
    latency = [r["latency_delta_pct"] for r in rows]
    qdrop = [r["quality_drop"] for r in rows]
    successes = [r.get("success", False) for r in rows]

    return {
        "savings_pct": statistics.mean(savings) * 100,
        "latency_delta_pct": statistics.mean(latency) * 100,
        "quality_drop_avg": statistics.mean(qdrop),
        "quality_guardrail_ok": statistics.mean(qdrop) < 0.05,
        "success_rate": sum(successes) / len(successes) * 100,
    }


def print_report(r, rows):
    print("\n═══════════════════════════════")
    print("   Kernell Benchmark Report")
    print("═══════════════════════════════\n")

    print(f"  Tasks evaluated:    {len(rows)}")
    print(f"  Success rate:       {r['success_rate']:.0f}%")
    print()
    print(f"  💰 Cost reduction:  {r['savings_pct']:.1f}%")
    print(f"  ⚡ Latency delta:   {r['latency_delta_pct']:.1f}%")
    print(f"  📉 Quality drop:    {r['quality_drop_avg']:.3f}")
    print()

    verdict = "PASS ✅" if r["quality_guardrail_ok"] else "FAIL ❌"
    print(f"  Result: {verdict}")

    # Per-task breakdown
    print("\n  ── Per-task breakdown ──\n")
    for row in rows:
        icon = "✅" if row.get("success") else "❌"
        print(
            f"  {icon} {row['task_id']:4s} │ "
            f"route={row['route']:14s} │ "
            f"savings={row['savings_pct']*100:5.1f}% │ "
            f"qdrop={row['quality_drop']:.3f}"
        )

    print("\n═══════════════════════════════\n")


def update_leaderboard(report, num_tasks):
    path = Path("benchmarks/leaderboard.json")

    if path.exists():
        data = json.loads(path.read_text())
    else:
        data = []

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        commit = "unknown"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit": commit,
        "tasks": num_tasks,
        "savings_pct": round(report["savings_pct"], 2),
        "latency_delta_pct": round(report["latency_delta_pct"], 2),
        "quality_drop": round(report["quality_drop_avg"], 4),
        "quality_ok": report["quality_guardrail_ok"],
        "success_rate": round(report["success_rate"], 1),
    }

    data.append(entry)
    data = data[-50:]  # Keep last 50

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    print(f"  📋 Leaderboard updated ({len(data)} entries)")

    # Generate badge
    badge = {
        "label": "cost reduction",
        "value": f"{report['savings_pct']:.1f}%",
        "color": "green" if report["savings_pct"] > 50 else "yellow",
    }
    Path("benchmarks/badge.json").write_text(json.dumps(badge, indent=2))
    print(f"  🏷️  Badge generated: {badge['value']}")


if __name__ == "__main__":
    runs = sorted(Path("benchmarks/runs").glob("*.jsonl"))
    if not runs:
        print("No benchmark runs found.")
        sys.exit(1)

    latest = runs[-1]
    print(f"  📁 Reading: {latest.name}")
    rows = [json.loads(line) for line in open(latest) if line.strip()]

    report = summarize(rows)
    print_report(report, rows)
    update_leaderboard(report, len(rows))
