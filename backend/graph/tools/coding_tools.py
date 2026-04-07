import json
import httpx
from langchain_core.tools import tool
from services.ais_mapper import map_ais_scores as _map_ais


@tool
def search_icd_nlm(description: str) -> str:
    """
    Search ICD-10-CM codes by injury/diagnosis description using the NLM Clinical Tables API.
    Returns a JSON array of matching codes with names. No API key required.
    """
    url = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    params = {
        "sf": "code,name",
        "df": "code,name",
        "terms": description[:100],
        "maxList": 5,
    }
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            # NLM response: [total, codes_list, extra, display_rows]
            codes = data[1] if len(data) > 1 else []
            display = data[3] if len(data) > 3 else []
            results = []
            for i, code in enumerate(codes[:5]):
                name = display[i][1] if display and i < len(display) else ""
                results.append({"code": code, "name": name})
            return json.dumps(results)
        return json.dumps([])
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def validate_icd_nlm(code: str) -> str:
    """
    Validate that an ICD-10-CM code exists in the official NLM database.
    Returns JSON with 'valid' boolean and 'name' if found.
    """
    url = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    params = {"sf": "code,name", "df": "code,name", "terms": code, "maxList": 1}
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            codes = data[1] if len(data) > 1 else []
            display = data[3] if len(data) > 3 else []
            if codes and codes[0].upper() == code.upper():
                name = display[0][1] if display else ""
                return json.dumps({"valid": True, "code": code, "name": name})
        return json.dumps({"valid": False, "code": code})
    except Exception as e:
        return json.dumps({"error": str(e), "valid": False})


@tool
def normalize_drug_rxnorm(drug_name: str) -> str:
    """
    Normalize a drug name to its canonical RxCUI identifier using the NLM RxNorm API.
    Returns JSON with rxcui and canonical name. No API key required.
    """
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json"
    params = {"name": drug_name, "search": 1}
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            rxcui = (
                data.get("idGroup", {})
                .get("rxnormId", [None])[0]
            )
            if rxcui:
                return json.dumps({"rxcui": rxcui, "canonical_name": drug_name})
        return json.dumps({"rxcui": None, "canonical_name": drug_name})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def lookup_ais_score(icd_code: str, severity_text: str) -> str:
    """
    Map an ICD-10 code (or fallback severity text) to an AIS severity score.
    Returns JSON with ais_score (1-6) and ais_label.
    """
    injury = {
        "icd_code": icd_code,
        "severity_indicator": severity_text,
    }
    scored = _map_ais([injury])
    return json.dumps({
        "icd_code": icd_code,
        "ais_score": scored[0]["ais_score"],
        "ais_label": scored[0]["ais_label"],
    })
