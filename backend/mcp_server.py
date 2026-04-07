"""
PI Valuation MCP Server
-----------------------
Exposes 6 tools via the MCP Streamable HTTP transport.
Mounted at /mcp inside the main FastAPI app (create_mcp_app()).
Can also run standalone: python mcp_server.py
"""
import os
import json
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP(
    name="PI Valuation Engine",
    instructions=(
        "Tools for personal injury case analysis: "
        "extract injuries from medical records, look up ICD-10 codes, "
        "calculate settlement ranges, search comparable verdicts, and generate demand letters. "
        "All AI calls use Groq (Llama 3.3 70B). All data APIs are free public sources."
    ),
)


# ── Tool 1: Full pipeline ─────────────────────────────────────────────────────

@mcp.tool()
def analyze_medical_record(
    text: str,
    jurisdiction: str = "CA",
    lost_wages: float = 0,
    future_care: float = 0,
) -> dict:
    """
    Run the full PI valuation pipeline on medical record text.
    Extracts injuries, assigns ICD-10 codes, calculates settlement range,
    searches comparable verdicts, and generates a demand letter.

    Args:
        text: Medical record text (ER notes, clinical notes, discharge summary, etc.)
        jurisdiction: State code — CA, NY, TX, FL, IL, or DEFAULT
        lost_wages: Total lost wages in dollars
        future_care: Estimated future medical care costs in dollars

    Returns:
        Dict with injuries, valuation, and demand_letter
    """
    from graph.graph import pipeline

    initial_state = {
        "raw_text": text,
        "jurisdiction": jurisdiction,
        "lost_wages": lost_wages,
        "future_care": future_care,
        "injuries": [],
        "parsed_lost_wages": 0.0,
        "parsed_future_care": 0.0,
        "valuation": {},
        "case_opinions": [],
        "demand_letter": "",
        "messages": [],
        "retry_count": 0,
        "errors": [],
    }
    result = pipeline.invoke(initial_state)
    return {
        "injuries": result.get("injuries", []),
        "valuation": result.get("valuation", {}),
        "case_opinions": result.get("case_opinions", []),
        "demand_letter": result.get("demand_letter", ""),
        "parsed_lost_wages": result.get("parsed_lost_wages", 0),
        "parsed_future_care": result.get("parsed_future_care", 0),
    }


# ── Tool 2: ICD-10 code lookup ────────────────────────────────────────────────

@mcp.tool()
def search_icd_codes(description: str) -> list[dict]:
    """
    Search ICD-10-CM codes by injury or diagnosis description.
    Uses the NLM Clinical Tables API (free, no key required).

    Args:
        description: Plain-language injury description, e.g. "cervical disc herniation"

    Returns:
        List of matching ICD-10 codes with names
    """
    import httpx
    url = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    params = {"sf": "code,name", "df": "code,name", "terms": description[:100], "maxList": 7}
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
        data = resp.json()
        codes = data[1] if len(data) > 1 else []
        display = data[3] if len(data) > 3 else []
        return [
            {"code": codes[i], "name": display[i][1] if display and i < len(display) else ""}
            for i in range(len(codes[:7]))
        ]
    except Exception as e:
        return [{"error": str(e)}]


# ── Tool 3: Procedure cost lookup ─────────────────────────────────────────────

@mcp.tool()
def get_procedure_cost(procedure_description: str) -> dict:
    """
    Look up the Medicare national payment rate for a medical procedure.
    Uses the CMS Physician Fee Schedule API (free, no key required).

    Args:
        procedure_description: Description of the procedure, e.g. "ACDF cervical fusion"

    Returns:
        Dict with procedure code, description, and Medicare payment rates
    """
    import httpx
    # First search NLM for a CPT-like code hint
    url = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    params = {"sf": "code,name", "df": "code,name", "terms": procedure_description[:80], "maxList": 1}
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
        data = resp.json()
        codes = data[1] if len(data) > 1 else []
        icd_hint = codes[0] if codes else ""

        cms_url = "https://data.cms.gov/resource/6pcd-ht5d.json"
        cms_params = {"$q": procedure_description[:60], "$limit": 1}
        cms_resp = client.get(cms_url, params=cms_params)
        if cms_resp.status_code == 200:
            rows = cms_resp.json()
            if rows:
                r = rows[0]
                return {
                    "description": r.get("hcpcs_description", procedure_description),
                    "code": r.get("hcpcs_cd", ""),
                    "non_facility_payment": r.get("non_facility_pricing_amount"),
                    "facility_payment": r.get("facility_pricing_amount"),
                    "icd_hint": icd_hint,
                }
        return {"description": procedure_description, "note": "Not found in CMS fee schedule"}
    except Exception as e:
        return {"error": str(e)}


# ── Tool 4: Settlement calculation ───────────────────────────────────────────

@mcp.tool()
def calculate_settlement_range(
    medical_specials: float,
    lost_wages: float,
    future_care: float,
    max_ais: int,
    has_permanent: bool,
    jurisdiction: str = "CA",
) -> dict:
    """
    Calculate a PI settlement range (conservative, mid-range, high-end) from damages inputs.
    Uses the Sacramento County Public Law Library damages formula.

    Args:
        medical_specials: Total medical bills billed
        lost_wages: Total lost wages
        future_care: Estimated future medical costs
        max_ais: Maximum AIS severity score (1=Minor to 5=Critical)
        has_permanent: Whether any permanent impairment exists
        jurisdiction: State code — CA, NY, TX, FL, IL

    Returns:
        Dict with economic damages, non-economic damages, and three settlement estimates
    """
    from services.valuation import _get_multiplier, JURISDICTION_ADJUSTMENTS

    multiplier = _get_multiplier(max_ais, has_permanent)
    economic = medical_specials + lost_wages + future_care
    non_economic = medical_specials * multiplier
    base = economic + non_economic
    jf = JURISDICTION_ADJUSTMENTS.get(jurisdiction.upper(), JURISDICTION_ADJUSTMENTS["DEFAULT"])

    return {
        "medical_specials": round(medical_specials),
        "lost_wages": round(lost_wages),
        "future_care": round(future_care),
        "economic_damages": round(economic),
        "multiplier": multiplier,
        "non_economic_damages": round(non_economic),
        "conservative": round(base * 0.70 * jf),
        "mid_range": round(base * jf),
        "high_end": round(base * 1.40 * jf),
        "max_ais": max_ais,
        "has_permanent": has_permanent,
        "jurisdiction": jurisdiction.upper(),
        "jurisdiction_factor": jf,
    }


# ── Tool 5: Drug adverse events ───────────────────────────────────────────────

@mcp.tool()
def lookup_drug_reactions(drug_name: str) -> dict:
    """
    Look up adverse drug reactions for medications mentioned in a medical record.
    Uses the OpenFDA FAERS database (free, optional key for higher rate limits).

    Args:
        drug_name: Medication name, e.g. "oxycodone" or "gabapentin"

    Returns:
        Dict with drug name and list of reported adverse reactions
    """
    import httpx
    api_key = os.environ.get("OPENFDA_API_KEY", "")
    url = "https://api.fda.gov/drug/event.json"
    params = {
        "search": f'patient.drug.medicinalproduct:"{drug_name}"',
        "limit": 3,
    }
    if api_key:
        params["api_key"] = api_key
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
        if resp.status_code == 200:
            results = resp.json().get("results", [])[:3]
            reactions = []
            for r in results:
                rxs = [rx.get("reactionmeddrapt", "") for rx in r.get("patient", {}).get("reaction", [])]
                reactions.extend(rxs[:3])
            return {"drug": drug_name, "reported_reactions": list(set(reactions))[:8]}
        return {"drug": drug_name, "note": "No FDA data found"}
    except Exception as e:
        return {"drug": drug_name, "error": str(e)}


# ── App factory for mounting inside FastAPI ───────────────────────────────────

def create_mcp_app():
    """Return the ASGI app for mounting inside FastAPI at /mcp."""
    return mcp.streamable_http_app()


# ── Standalone entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if transport == "http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.environ.get("MCP_PORT", 8001)))
    else:
        mcp.run(transport="stdio")
