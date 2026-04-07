import os
import json
import httpx
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from services.parser import extract_text_from_pdf as _parse_pdf

SYSTEM_PROMPT = """You are a medical record analyst for a personal injury law firm.
Extract all injury events, diagnoses, and treatments from the clinical note provided.

Return ONLY a valid JSON array. No explanation. No markdown. No code fences.

Each object must have these exact fields:
{{
  "event_type": "diagnosis" | "treatment" | "surgery" | "imaging" | "therapy" | "follow_up",
  "description": "plain English description",
  "body_part": "affected body part",
  "date": "YYYY-MM-DD or null",
  "severity_indicator": "minor" | "moderate" | "serious" | "severe" | "catastrophic",
  "permanent": true | false,
  "medical_cost_billed": dollar amount as number or 0
}}

If permanent impairment is mentioned, set permanent to true.
Extract every diagnosis, procedure, and treatment event."""


@tool
def parse_pdf_bytes(file_path: str) -> str:
    """Extract text from a PDF file at the given path. Returns the raw text content."""
    with open(file_path, "rb") as f:
        return _parse_pdf(f.read())


@tool
def extract_injuries_from_text(text: str) -> str:
    """
    Extract structured injury and treatment events from medical record text.
    Returns a JSON array string of injury objects.
    """
    llm = ChatGroq(
        api_key=os.environ.get("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=2000,
    )
    parser = JsonOutputParser()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Medical record:\n\n{text}"),
    ])
    chain = prompt | llm | parser

    try:
        result = chain.invoke({"text": text[:12000]})
        return json.dumps(result)
    except Exception:
        # Fallback: raw call with manual strip
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.replace("{{", "{").replace("}}", "}")},
                {"role": "user", "content": f"Medical record:\n\n{text[:12000]}"},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return raw


@tool
def lookup_drug_openfda(drug_name: str) -> str:
    """
    Look up adverse drug reactions and events for a drug name using the OpenFDA API.
    Returns a JSON string with relevant safety information.
    """
    api_key = os.environ.get("OPENFDA_API_KEY", "")
    base = "https://api.fda.gov/drug/event.json"
    params = {
        "search": f'patient.drug.medicinalproduct:"{drug_name}"',
        "limit": 3,
    }
    if api_key:
        params["api_key"] = api_key

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(base, params=params)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            simplified = []
            for r in results[:3]:
                reactions = [
                    rx.get("reactionmeddrapt", "")
                    for rx in r.get("patient", {}).get("reaction", [])
                ]
                simplified.append({
                    "drug": drug_name,
                    "reactions": reactions[:5],
                    "serious": r.get("serious", 0),
                })
            return json.dumps(simplified)
        return json.dumps({"note": f"No FDA data found for {drug_name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})
