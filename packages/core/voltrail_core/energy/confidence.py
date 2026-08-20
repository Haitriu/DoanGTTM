def apply_uncertainty(p50: float, confidence_level: str = "medium") -> tuple[float, float]:
    """
    Returns (p10, p90) values given a p50 estimate and confidence level.
    
    p90 is the high-energy case (worst for battery).
    p10 is the low-energy case.
    """
    sigmas = {
        "high": 0.06,
        "medium": 0.10,
        "low": 0.15
    }
    sigma = sigmas.get(confidence_level, 0.10)
    margin = 1.28 * sigma
    
    p10 = p50 * (1 - margin)
    p90 = p50 * (1 + margin)
    
    # If energy is negative (regen), keep p10 < p90 mathematically
    if p10 > p90:
        p10, p90 = p90, p10
        
    return p10, p90
