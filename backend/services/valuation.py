# Methodology: Sacramento County Public Law Library "Calculating Personal Injury Damages"
# Formula: Economic Damages + (Medical Specials × Pain & Suffering Multiplier)

JURISDICTION_ADJUSTMENTS = {
    "CA": 1.20,
    "NY": 1.20,
    "TX": 0.90,
    "FL": 0.95,
    "IL": 1.05,
    "DEFAULT": 1.00,
}


def _get_multiplier(max_ais: int, has_permanent: bool) -> float:
    if max_ais >= 5:
        return 4.5
    elif max_ais == 4:
        return 3.8
    elif max_ais == 3 and has_permanent:
        return 3.5
    elif max_ais == 3:
        return 3.0
    elif max_ais == 2 and has_permanent:
        return 2.8
    elif max_ais == 2:
        return 2.2
    else:
        return 1.5


def calculate_settlement(injuries, lost_wages, future_care, jurisdiction):
    medical_specials = sum(i.get("medical_cost_billed", 0) for i in injuries)

    ais_scores = [i.get("ais_score", 1) for i in injuries if i.get("ais_score")]
    max_ais = max(ais_scores) if ais_scores else 1
    has_permanent = any(i.get("permanent", False) for i in injuries)

    multiplier = _get_multiplier(max_ais, has_permanent)
    economic_damages = medical_specials + lost_wages + future_care
    non_economic = medical_specials * multiplier
    base_total = economic_damages + non_economic

    jurisdiction_factor = JURISDICTION_ADJUSTMENTS.get(
        jurisdiction.upper(), JURISDICTION_ADJUSTMENTS["DEFAULT"]
    )

    return {
        "medical_specials": round(medical_specials),
        "lost_wages": round(lost_wages),
        "future_care": round(future_care),
        "economic_damages": round(economic_damages),
        "multiplier": multiplier,
        "non_economic_damages": round(non_economic),
        "conservative": round(base_total * 0.70 * jurisdiction_factor),
        "mid_range": round(base_total * jurisdiction_factor),
        "high_end": round(base_total * 1.40 * jurisdiction_factor),
        "max_ais": max_ais,
        "has_permanent": has_permanent,
        "jurisdiction": jurisdiction.upper(),
        "jurisdiction_factor": jurisdiction_factor,
    }
