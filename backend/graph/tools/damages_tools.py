import os
import json
import httpx
from langchain_core.tools import tool
from services.valuation import calculate_settlement as _calc

# CMS Physician Fee Schedule dataset ID (2024 national payment file)
CMS_PFS_DATASET = "6pcd-ht5d"


@tool
def get_procedure_cost_cms(procedure_code: str) -> str:
    """
    Look up the Medicare national payment rate for a CPT/HCPCS procedure code
    using the CMS Physician Fee Schedule REST API. No API key required.
    Returns JSON with the procedure description and facility/non-facility payment amounts.
    """
    url = f"https://data.cms.gov/resource/{CMS_PFS_DATASET}.json"
    params = {"hcpcs_cd": procedure_code.upper(), "$limit": 1}
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                row = data[0]
                return json.dumps({
                    "code": procedure_code,
                    "description": row.get("hcpcs_description", ""),
                    "non_facility_payment": row.get("non_facility_pricing_amount", None),
                    "facility_payment": row.get("facility_pricing_amount", None),
                })
        return json.dumps({"code": procedure_code, "note": "Not found in CMS fee schedule"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def calculate_settlement_range(
    injuries_json: str,
    lost_wages: float,
    future_care: float,
    jurisdiction: str,
) -> str:
    """
    Calculate the PI settlement range (conservative, mid-range, high-end) from
    structured injury data. injuries_json must be a JSON array of injury objects
    with medical_cost_billed, ais_score, and permanent fields.
    Returns JSON with full damages breakdown and three settlement estimates.
    """
    try:
        injuries = json.loads(injuries_json)
        result = _calc(
            injuries=injuries,
            lost_wages=lost_wages,
            future_care=future_care,
            jurisdiction=jurisdiction,
        )
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def get_case_opinions(query: str) -> str:
    """
    Search CourtListener for relevant personal injury case opinions by keyword.
    Returns a JSON array of case summaries. Requires COURTLISTENER_TOKEN env var (free account).
    """
    token = os.environ.get("COURTLISTENER_TOKEN", "")
    headers = {"Authorization": f"Token {token}"} if token else {}
    url = "https://www.courtlistener.com/api/rest/v4/search/"
    params = {"q": query, "type": "o", "$limit": 3}
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, params=params, headers=headers)
        if resp.status_code == 200:
            results = resp.json().get("results", [])[:3]
            simplified = [
                {
                    "case_name": r.get("caseName", ""),
                    "date": r.get("dateFiled", ""),
                    "court": r.get("court", ""),
                    "snippet": r.get("snippet", "")[:300],
                    "url": (
                        "https://www.courtlistener.com" + r["absolute_url"]
                        if r.get("absolute_url")
                        else None
                    ),
                }
                for r in results
            ]
            return json.dumps(simplified)
        return json.dumps({"note": "CourtListener returned no results", "results": []})
    except Exception as e:
        return json.dumps({"error": str(e), "results": []})
