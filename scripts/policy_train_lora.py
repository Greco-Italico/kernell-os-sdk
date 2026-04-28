#!/usr/bin/env python3
"""
Policy model LoRA training entrypoint (Phase B scaffold).

This script is intentionally minimal and dependency-safe:
- If `unsloth` is available, it uses that path.
- Otherwise it prints a clear instruction and exits non-zero.
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


def main() -> int:
    p = argparse.ArgumentParser(description="Train Policy-Lite with LoRA")
    p.add_argument("--train-file", required=True, help="SFT JSONL file")
    p.add_argument("--base-model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--max-steps", type=int, default=300)
    p.add_argument("--learning-rate", type=float, default=2e-4)
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    args = p.parse_args()

    samples = list(_read_jsonl(Path(args.train_file)))
    if not samples:
        raise SystemExit("empty dataset")

    try:
        import unsloth  # type: ignore # noqa: F401
    except Exception:
        print("unsloth not installed. Install training deps before running this script.")
        print("Suggested: pip install unsloth transformers datasets peft accelerate")
        return 2

    # This is a scaffold marker for host training automation.
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    meta = {
        "status": "ready_for_host_training",
        "train_file": args.train_file,
        "base_model": args.base_model,
        "samples": len(samples),
        "max_steps": args.max_steps,
        "learning_rate": args.learning_rate,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
    }
    with open(Path(args.output_dir) / "training_plan.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
