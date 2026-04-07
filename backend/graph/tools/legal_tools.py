import os
import json
from langchain_core.tools import tool
from groq import Groq


@tool
def generate_demand_letter(injuries_json: str, valuation_json: str) -> str:
    """
    Generate a professional personal injury demand letter from structured case data.
    injuries_json: JSON array of injury objects with icd_code, ais_score, permanent fields.
    valuation_json: JSON object with settlement amounts and damages breakdown.
    Returns the full demand letter text.
    """
    injuries = json.loads(injuries_json)
    valuation = json.loads(valuation_json)

    diagnoses = [
        f"- {i['description']} "
        f"(ICD-10: {i.get('icd_code', 'N/A')}, "
        f"AIS {i.get('ais_score', 'N/A')} – {i.get('ais_label', 'N/A')}"
        f"{', PERMANENT' if i.get('permanent') else ''})"
        for i in injuries
        if i.get("event_type") == "diagnosis"
    ]
    injury_block = "\n".join(diagnoses)

    prompt = f"""Write a professional personal injury demand letter using these case facts.
Use formal legal letter style. Today's date in the header.

DIAGNOSED INJURIES:
{injury_block}

DAMAGES:
- Past medical bills: ${valuation.get('medical_specials', 0):,}
- Lost wages: ${valuation.get('lost_wages', 0):,}
- Future medical care: ${valuation.get('future_care', 0):,}
- Pain & suffering (multiplier {valuation.get('multiplier', 1.5)}x): ${valuation.get('non_economic_damages', 0):,}
- TOTAL SETTLEMENT DEMAND: ${valuation.get('high_end', 0):,}

Use [PLAINTIFF NAME], [DEFENDANT NAME], [PLAINTIFF ATTORNEY] as placeholders.
Include: introduction paragraph, injuries and treatment narrative, damages breakdown table,
demand paragraph, and closing.
Do not add any preamble — start directly with the letter header.
"""

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1500,
    )
    return response.choices[0].message.content
