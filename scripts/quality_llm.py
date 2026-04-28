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
    if OpenAI is None or not os.environ.get("OPENAI_API_KEY"):
        return 0.5

    client = OpenAI()
    rubric = expected.get("rubric", "Answer is correct, relevant, and complete.")
    constraints = expected.get("constraints", "")

    judge_prompt = f"""You are a strict evaluator.

Task:
{prompt}

Model output:
{output}

Evaluation rubric:
{rubric}

Constraints:
{constraints}

Return ONLY a float between 0 and 1."""

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
