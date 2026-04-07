import os
import json
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are a medical record analyst for a personal injury law firm.
Extract all injury events, diagnoses, and treatments from the clinical note provided.

Return ONLY a valid JSON array. No explanation. No markdown. No code fences.

Each object must have these exact fields:
{
  "event_type": "diagnosis" | "treatment" | "surgery" | "imaging" | "therapy" | "follow_up",
  "description": "plain English description of the event",
  "body_part": "affected body part",
  "date": "YYYY-MM-DD or null if not mentioned",
  "severity_indicator": "minor" | "moderate" | "serious" | "severe" | "catastrophic",
  "permanent": true | false,
  "medical_cost_billed": dollar amount as number or 0 if not mentioned
}

If permanent impairment is mentioned, set permanent to true.
Be thorough — extract every diagnosis, procedure, and treatment event.
"""


def extract_injuries(text: str) -> list:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Medical record:\n\n{text}"}
        ],
        temperature=0.1,
        max_tokens=2000,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)
