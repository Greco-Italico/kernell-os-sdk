from __future__ import annotations
import os

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

def llm_judge_score(
    prompt: str,
    output: str,
    expected: dict,
    model: str = "gpt-4o-mini",
) -> float:
    """
    Devuelve score 0..1 evaluando si la respuesta cumple lo esperado.
    Fallback a 0.5 si no hay cliente disponible.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    
    if api_key:
        client = OpenAI(api_key=api_key)
        model = "gpt-4o-mini"
    elif openrouter_key:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_key)
        model = "openai/gpt-4o-mini"
    else:
        return 0.5
    rubric = expected.get("rubric", "Answer is correct, relevant, and complete.")
    constraints = expected.get("constraints", "")

    judge_prompt = f"""You are a BRUTALLY STRICT evaluator.
Your job is to find ANY flaw, omission, or lack of nuance in the output and penalize it heavily.

Task:
{prompt}

Model output:
{output}

Evaluation rubric:
{rubric}

Constraints:
{constraints}

Scoring rules:
1.0: Flawless, comprehensive, deep reasoning, perfect formatting.
0.8: Good but missing minor nuance or slightly suboptimal code.
0.5: Technically answers the question but is superficial, overly brief, or lacks depth.
0.2: Partially incorrect or logically flawed.
0.0: Completely wrong, missed the point, or hallucinates.

Return ONLY the float value (e.g. 0.8) and nothing else."""

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[{"role": "user", "content": judge_prompt}],
        )
        text = resp.choices[0].message.content.strip()
        return max(0.0, min(1.0, float(text)))
    except Exception:
        return 0.5
