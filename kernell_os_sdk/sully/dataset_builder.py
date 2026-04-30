import json
from kernell_os_sdk.telemetry.schema import TelemetryEvent

def compute_reward(event: TelemetryEvent) -> float:
    s = 1.0 if event.execution.success else 0.0
    a = event.consensus.score
    c = event.decision.confidence
    k = event.execution.cost_usd * 10
    
    latency_ratio = event.execution.latency_ms / max(1.0, event.features.input_tokens)
    latency_penalty = min(latency_ratio, 2.0) * 0.1
    r = event.execution.retries
    
    return (
        s +
        (0.5 * a) +
        (0.3 * c) -
        (0.3 * k) -
        latency_penalty -
        (0.2 * r)
    )

def format_instruction(event: TelemetryEvent) -> str:
    return (
        f"Task: {event.task.input_preview}\n"
        f"Input tokens: {event.features.input_tokens}\n"
        f"Expected output tokens: {event.features.expected_output_tokens}\n"
        f"Complexity: {event.features.complexity_score}\n"
        f"Priority: {event.features.priority}"
    )

def format_output(event: TelemetryEvent) -> str:
    return (
        f"Tier: {event.decision.tier}\n"
        f"Model: {event.decision.model}"
    )

def build_dataset(jsonl_path: str, output_path: str):
    dataset = []
    with open(jsonl_path, "r") as f:
        for line in f:
            try:
                raw = json.loads(line)
                event = TelemetryEvent(**raw)
            except Exception:
                continue  # Skip corrupt/invalid lines silently
            
            reward = compute_reward(event)
            sample = {
                "instruction": format_instruction(event),
                "input": "",
                "output": format_output(event),
                "reward": reward
            }
            dataset.append(sample)
            
    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2)
        
    print(f"✅ Dataset built: {len(dataset)} samples")
