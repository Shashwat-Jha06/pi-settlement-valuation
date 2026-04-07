# AIS = Abbreviated Injury Scale (public standard used in trauma medicine)
# 1=Minor, 2=Moderate, 3=Serious, 4=Severe, 5=Critical, 6=Unsurvivable

AIS_LABELS = {
    1: "Minor",
    2: "Moderate",
    3: "Serious",
    4: "Severe",
    5: "Critical",
    6: "Unsurvivable",
}

ICD_PREFIX_AIS_OVERRIDES = {
    "S14": 5,  # Cervical spinal cord injury
    "S24": 5,  # Thoracic spinal cord injury
    "S34": 5,  # Lumbar spinal cord injury
    "S06": 4,  # Intracranial injury / TBI
    "S22": 3,  # Rib/sternum fracture
    "S32": 3,  # Lumbar spine fracture
    "S52": 2,  # Forearm fracture
    "S72": 3,  # Femur fracture
    "T71": 4,  # Asphyxiation
    "M50": 2,  # Cervical disc disorder
    "M51": 2,  # Lumbar disc disorder
    "M54": 1,  # Back pain/radiculopathy
    "S63": 1,  # Wrist/hand injury
    "M79": 1,  # Soft tissue / myalgia
    "S93": 1,  # Ankle sprain
}

SEVERITY_TEXT_TO_AIS = {
    "minor": 1,
    "moderate": 2,
    "serious": 3,
    "severe": 4,
    "catastrophic": 5,
}


def map_ais_scores(injuries: list) -> list:
    for injury in injuries:
        icd = injury.get("icd_code") or ""
        prefix = icd[:3]

        if prefix in ICD_PREFIX_AIS_OVERRIDES:
            score = ICD_PREFIX_AIS_OVERRIDES[prefix]
        else:
            score = SEVERITY_TEXT_TO_AIS.get(
                injury.get("severity_indicator", "minor"), 1
            )

        injury["ais_score"] = score
        injury["ais_label"] = AIS_LABELS.get(score, "Unknown")

    return injuries
