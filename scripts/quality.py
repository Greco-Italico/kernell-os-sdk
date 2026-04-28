from __future__ import annotations

def quality_score(output: str, expected: dict) -> float:
    """
    Heurístico simple pero útil.
    """
    if not output:
        return 0.0
        
    score = 1.0
    
    if len(output) < 30:
        score -= 0.4
        
    keywords = expected.get("keywords", [])
    if keywords:
        hits = sum(1 for k in keywords if k.lower() in output.lower())
        score *= hits / max(len(keywords), 1)
        
    if expected.get("must_contain_colon") and ":" not in output:
        score -= 0.2
        
    return max(0.0, min(1.0, score))
