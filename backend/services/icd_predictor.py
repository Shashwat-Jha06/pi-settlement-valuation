import os
import json
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def predict_icd_codes(injuries: list) -> list:
    diagnoses = [i for i in injuries if i["event_type"] == "diagnosis"]
    if not diagnoses:
        return injuries

    descriptions = [i["description"] for i in diagnoses]

    prompt = f"""Assign the most specific ICD-10-CM code to each injury description below.
Return ONLY a JSON array of strings, one code per item, same order as input.
No explanation. No markdown. No extra text.

Injuries:
{json.dumps(descriptions, indent=2)}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=300,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    codes = json.loads(raw)

    diag_index = 0
    for injury in injuries:
        if injury["event_type"] == "diagnosis":
            injury["icd_code"] = codes[diag_index] if diag_index < len(codes) else "Z99.89"
            diag_index += 1
        else:
            injury["icd_code"] = None

    return injuries
