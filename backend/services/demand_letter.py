import os
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def generate_demand_letter(injuries: list, valuation: dict) -> str:
    diagnoses = [
        f"- {i['description']} "
        f"(ICD-10: {i.get('icd_code', 'N/A')}, "
        f"AIS Severity: {i.get('ais_score', 'N/A')} – {i.get('ais_label', 'N/A')}"
        f"{', PERMANENT' if i.get('permanent') else ''})"
        for i in injuries if i["event_type"] == "diagnosis"
    ]
    injury_block = "\n".join(diagnoses)

    prompt = f"""
Write a professional personal injury demand letter using these case facts.
Use formal legal letter style. Today's date in the header.

DIAGNOSED INJURIES:
{injury_block}

DAMAGES:
- Past medical bills: ${valuation['medical_specials']:,}
- Lost wages: ${valuation['lost_wages']:,}
- Future medical care: ${valuation['future_care']:,}
- Pain & suffering (multiplier {valuation['multiplier']}x): ${valuation['non_economic_damages']:,}
- TOTAL SETTLEMENT DEMAND: ${valuation['high_end']:,}

Use [PLAINTIFF NAME], [DEFENDANT NAME], [PLAINTIFF ATTORNEY] as placeholders.
Include: introduction paragraph, injuries and treatment narrative, damages breakdown table,
demand paragraph, and closing.
Do not add any preamble — start directly with the letter header.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1500,
    )
    return response.choices[0].message.content
