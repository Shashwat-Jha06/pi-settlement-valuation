"""
4 LangGraph agent nodes.

Medical + Legal agents use the LLM (genuine reasoning needed).
ICD/AIS + Damages agents call APIs and math directly (no LLM needed — deterministic).

Total LLM calls per analysis: 2 (extraction + demand letter).

Chain-of-thought side channel
-------------------------------
Every node calls _think() / _token() to emit granular progress events that the
/analyze/stream SSE endpoint picks up and forwards to the frontend in real time.
These helpers are no-ops when no stream is active (e.g. during /analyze calls).
"""
import os
import json
import threading
import httpx
from graph.state import CaseState
from services.ais_mapper import map_ais_scores as _map_ais
from services.valuation import calculate_settlement as _calc

# ─────────────────────────────────────────────────────────────────────────────
# Chain-of-thought side channel
# ─────────────────────────────────────────────────────────────────────────────

# Maps thread-id → queue.Queue so nodes can emit thoughts without needing an
# explicit argument.  The SSE generator injects itself before starting the
# pipeline thread and cleans up afterwards.
_thought_queues: dict = {}


def _think(node: str, message: str) -> None:
    """Emit a thought log entry to the active SSE stream (no-op if none)."""
    q = _thought_queues.get(threading.current_thread().ident)
    if q:
        q.put(("thought", {"type": "thought", "node": node, "message": message}))


def _token(node: str, tok: str) -> None:
    """Emit a raw LLM token to the active SSE stream (no-op if none)."""
    q = _thought_queues.get(threading.current_thread().ident)
    if q:
        q.put(("thought", {"type": "token", "node": node, "token": tok}))


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: Medical Extraction Agent — 1 streaming LLM call
# ─────────────────────────────────────────────────────────────────────────────

EXTRACT_SYSTEM = """You are a medical record analyst for a personal injury law firm.
Extract all injury events, diagnoses, and treatments from the clinical note.
Also extract any financial figures mentioned (lost wages, future care costs).

Return ONLY a valid JSON object with this exact structure. No explanation. No markdown. No code fences.

{
  "injuries": [
    {
      "event_type": "diagnosis" | "treatment" | "surgery" | "imaging" | "therapy" | "follow_up",
      "description": "plain English description",
      "body_part": "affected body part",
      "date": "YYYY-MM-DD or null",
      "severity_indicator": "minor" | "moderate" | "serious" | "severe" | "catastrophic",
      "permanent": true | false,
      "medical_cost_billed": dollar amount as number or 0 if not mentioned
    }
  ],
  "financials": {
    "lost_wages": total lost wages as a number (sum all periods mentioned) or 0 if not mentioned,
    "future_care": total estimated future medical costs as a number or 0 if not mentioned
  }
}

Rules:
- If permanent impairment is mentioned, set permanent to true.
- For lost_wages: parse expressions like "6 weeks @ $1,200/week" → 7200, or "$7,200 lost wages" → 7200.
- For future_care: parse expressions like "estimated cost: $35,000" for recommended future procedures.
- Extract every diagnosis, procedure, and treatment event.
- medical_cost_billed is for PAST billed costs only, not future estimates.

--- EXAMPLE ---
INPUT:
Patient presents after rear-end MVA. MRI lumbar spine: disc herniation L4-L5. ER visit 03/12/2023 billed $5,200. Physical therapy 8 sessions @ $175/session = $1,400. Out of work 3 weeks @ $900/week = $2,700. Future surgery estimated $28,000.

OUTPUT:
{"injuries":[{"event_type":"diagnosis","description":"Lumbar disc herniation L4-L5","body_part":"lumbar spine","date":null,"severity_indicator":"moderate","permanent":false,"medical_cost_billed":0},{"event_type":"treatment","description":"Emergency room evaluation following MVA","body_part":"multiple","date":"2023-03-12","severity_indicator":"moderate","permanent":false,"medical_cost_billed":5200},{"event_type":"therapy","description":"Physical therapy for lumbar disc herniation","body_part":"lumbar spine","date":null,"severity_indicator":"minor","permanent":false,"medical_cost_billed":1400}],"financials":{"lost_wages":2700,"future_care":28000}}
--- END EXAMPLE ---"""


def medical_agent_node(state: CaseState) -> dict:
    """1 streaming LLM call — extracts injury structure AND financial figures."""
    from groq import Groq
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    text = state["raw_text"][:12000]
    retry_count = state.get("retry_count", 0)
    errors = list(state.get("errors", []))

    _think("medical_agent", f"Medical record received — {len(text):,} characters")
    _think("medical_agent", "Building extraction prompt (injuries + financials)…")

    try:
        _think("medical_agent", "Querying Groq · llama-3.3-70b-versatile  [streaming]")

        stream = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": EXTRACT_SYSTEM},
                {"role": "user", "content": f"Medical record:\n\n{text}"},
            ],
            temperature=0.1,
            max_tokens=2000,
            stream=True,
        )

        raw = ""
        for chunk in stream:
            tok = chunk.choices[0].delta.content or ""
            if tok:
                raw += tok
                _token("medical_agent", tok)

        _think("medical_agent", "Stream complete — parsing JSON…")
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)

        # Support both wrapped {"injuries": [...]} and bare [...] responses
        if isinstance(parsed, list):
            injuries = parsed
            financials = {"lost_wages": 0, "future_care": 0}
        else:
            injuries = parsed.get("injuries", [])
            financials = parsed.get("financials", {"lost_wages": 0, "future_care": 0})

        if not isinstance(injuries, list) or len(injuries) == 0:
            raise ValueError("Empty injury list returned")

        total_billed = sum(i.get("medical_cost_billed", 0) or 0 for i in injuries)
        lw = float(financials.get("lost_wages", 0) or 0)
        fc = float(financials.get("future_care", 0) or 0)

        _think("medical_agent", f"Extracted {len(injuries)} medical events")
        if total_billed:
            _think("medical_agent", f"Total past medical bills: ${total_billed:,.0f}")
        if lw:
            _think("medical_agent", f"Auto-parsed lost wages: ${lw:,.0f}")
        if fc:
            _think("medical_agent", f"Auto-parsed future care estimate: ${fc:,.0f}")

        severity_counts: dict = {}
        for i in injuries:
            sev = i.get("severity_indicator", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        _think("medical_agent", "Severity breakdown: " + ", ".join(
            f"{v}× {k}" for k, v in severity_counts.items()
        ))

        return {
            "injuries": injuries,
            "parsed_lost_wages": lw,
            "parsed_future_care": fc,
            "retry_count": retry_count,
            "errors": errors,
        }

    except Exception as e:
        errors.append(f"medical_agent error: {e}")
        _think("medical_agent", f"⚠ Error: {e}")
        return {
            "injuries": [],
            "parsed_lost_wages": 0.0,
            "parsed_future_care": 0.0,
            "retry_count": retry_count + 1,
            "errors": errors,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Node 2: ICD + AIS Coding — direct NLM API calls, no LLM
# ─────────────────────────────────────────────────────────────────────────────

def _search_icd_nlm(description: str) -> str:
    """Call NLM ICD-10-CM API directly."""
    url = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"
    params = {"sf": "code,name", "df": "code,name", "terms": description[:100], "maxList": 3}
    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(url, params=params)
        data = resp.json()
        codes = data[1] if len(data) > 1 else []
        return codes[0] if codes else "Z99.89"
    except Exception:
        return "Z99.89"


def icd_agent_node(state: CaseState) -> dict:
    """0 LLM calls — direct NLM API lookup per diagnosis, then static AIS mapping."""
    injuries = state.get("injuries", [])
    if not injuries:
        _think("icd_agent", "No injuries to code — skipping")
        return {"injuries": injuries}

    diagnoses = [i for i in injuries if i.get("event_type") == "diagnosis"]
    _think("icd_agent", f"Processing {len(injuries)} events ({len(diagnoses)} diagnoses need ICD-10 codes)")

    updated = []
    for injury in injuries:
        inj = dict(injury)

        if inj.get("event_type") == "diagnosis":
            desc = inj.get("description", "")
            _think("icd_agent", f"NLM API lookup: \"{desc[:70]}\"")
            icd_code = _search_icd_nlm(desc)
            inj["icd_code"] = icd_code
            _think("icd_agent", f"  → {icd_code}")
        else:
            inj.setdefault("icd_code", None)

        updated.append(inj)

    _think("icd_agent", "Running AIS severity mapping (static lookup table)…")
    updated = _map_ais(updated)

    coded = [
        (i.get("icd_code"), i.get("ais_score"), i.get("ais_label", ""))
        for i in updated
        if i.get("event_type") == "diagnosis" and i.get("ais_score")
    ]
    for icd, ais, label in coded:
        _think("icd_agent", f"  {icd}  →  AIS {ais} — {label}")

    return {"injuries": updated}


# ─────────────────────────────────────────────────────────────────────────────
# Node 3: Damages Calculation — pure math + CourtListener API, no LLM
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_case_opinions(query: str) -> list:
    """Direct CourtListener API call — no LLM."""
    token = os.environ.get("COURTLISTENER_TOKEN", "")
    headers = {"Authorization": f"Token {token}"} if token else {}
    url = "https://www.courtlistener.com/api/rest/v4/search/"
    params = {"q": query, "type": "o", "$limit": 3}
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params, headers=headers)
        if resp.status_code == 200:
            results = resp.json().get("results", [])[:3]
            return [
                {
                    "case_name": r.get("caseName", ""),
                    "date": r.get("dateFiled", ""),
                    "court": r.get("court", ""),
                    "snippet": r.get("snippet", "")[:300],
                    "url": (
                        "https://www.courtlistener.com" + r["absolute_url"]
                        if r.get("absolute_url") else None
                    ),
                }
                for r in results
            ]
    except Exception:
        pass
    return []


def damages_agent_node(state: CaseState) -> dict:
    """0 LLM calls — settlement math is deterministic, CourtListener is a direct API call."""
    injuries = state.get("injuries", [])
    jurisdiction = state.get("jurisdiction", "CA")

    # Use user-provided values; fall back to text-parsed values if user left them at 0
    user_lw = state.get("lost_wages", 0)
    user_fc = state.get("future_care", 0)
    lost_wages = user_lw or state.get("parsed_lost_wages", 0)
    future_care = user_fc or state.get("parsed_future_care", 0)

    _think("damages_agent", f"Jurisdiction: {jurisdiction}")

    medical_specials = sum(i.get("medical_cost_billed", 0) or 0 for i in injuries)
    _think("damages_agent", f"Medical specials (past bills): ${medical_specials:,.0f}")

    if lost_wages:
        src = "user-provided" if user_lw else "auto-parsed from text"
        _think("damages_agent", f"Lost wages ({src}): ${lost_wages:,.0f}")
    else:
        _think("damages_agent", "Lost wages: $0  (none found in record)")

    if future_care:
        src = "user-provided" if user_fc else "auto-parsed from text"
        _think("damages_agent", f"Future care estimate ({src}): ${future_care:,.0f}")
    else:
        _think("damages_agent", "Future care: $0  (none found in record)")

    _think("damages_agent", "Applying pain & suffering multiplier…")
    valuation = _calc(
        injuries=injuries,
        lost_wages=lost_wages,
        future_care=future_care,
        jurisdiction=jurisdiction,
    )

    multiplier = valuation.get("multiplier", 1.5)
    non_econ = valuation.get("non_economic_damages", 0)
    _think("damages_agent", f"Multiplier selected: {multiplier}x  →  non-economic: ${non_econ:,.0f}")
    _think("damages_agent", f"Conservative: ${valuation.get('conservative', 0):,.0f}")
    _think("damages_agent", f"Mid-range:    ${valuation.get('mid_range', 0):,.0f}")
    _think("damages_agent", f"High-end:     ${valuation.get('high_end', 0):,.0f}")

    top_diagnosis = next(
        (i["description"] for i in injuries if i.get("event_type") == "diagnosis"),
        "personal injury",
    )
    query = f"{top_diagnosis} personal injury {jurisdiction}"
    _think("damages_agent", f"CourtListener search: \"{query[:80]}\"")
    case_opinions = _fetch_case_opinions(query)

    if case_opinions:
        _think("damages_agent", f"Found {len(case_opinions)} relevant opinion(s):")
        for op in case_opinions:
            yr = (op.get("date") or "")[:4]
            _think("damages_agent", f"  • {op.get('case_name', 'Unknown')} ({yr})")
    else:
        _think("damages_agent", "No case opinions returned (token may be unset or rate-limited)")

    return {"valuation": valuation, "case_opinions": case_opinions}


# ─────────────────────────────────────────────────────────────────────────────
# Node 4: Legal Writing Agent — 1 streaming LLM call
# ─────────────────────────────────────────────────────────────────────────────

def legal_agent_node(state: CaseState) -> dict:
    """1 streaming LLM call — generates the demand letter from structured case data."""
    from groq import Groq
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    injuries = state.get("injuries", [])
    valuation = state.get("valuation", {})
    case_opinions = state.get("case_opinions", [])

    diagnoses = [
        f"- {i['description']} "
        f"(ICD-10: {i.get('icd_code', 'N/A')}, "
        f"AIS {i.get('ais_score', 'N/A')} – {i.get('ais_label', 'N/A')}"
        f"{', PERMANENT' if i.get('permanent') else ''})"
        for i in injuries if i.get("event_type") == "diagnosis"
    ]
    injury_block = "\n".join(diagnoses) if diagnoses else "See attached medical records."

    # Build case law context block — only include cases that have a useful snippet
    case_law_lines = []
    for op in case_opinions:
        name = op.get("case_name", "").strip()
        snippet = (op.get("snippet") or "").strip()[:200]
        year = (op.get("date") or "")[:4]
        court = (op.get("court") or "").strip()
        if name and snippet:
            line = f"- {name}"
            if year:
                line += f" ({year})"
            if court:
                line += f", {court}"
            line += f": {snippet}"
            case_law_lines.append(line)

    case_law_block = "\n".join(case_law_lines) if case_law_lines else ""

    _think("legal_agent", f"Composing demand letter — {len(diagnoses)} diagnosed injur{'y' if len(diagnoses) == 1 else 'ies'}")
    _think("legal_agent", f"Total demand amount: ${valuation.get('high_end', 0):,.0f}")
    if case_law_block:
        _think("legal_agent", f"Injecting {len(case_law_lines)} case law citation(s) into context")
    _think("legal_agent", "Building prompt with injuries + damages table…")

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
{f"""
RELEVANT CASE LAW (reference naturally where appropriate in the letter):
{case_law_block}
""" if case_law_block else ""}
Use [PLAINTIFF NAME], [DEFENDANT NAME], [PLAINTIFF ATTORNEY] as placeholders.
Include: introduction paragraph, injuries and treatment narrative, damages breakdown table,
demand paragraph, and closing.
Do not add any preamble — start directly with the letter header.
"""

    _think("legal_agent", "Querying Groq · llama-3.3-70b-versatile  [streaming]")

    try:
        stream = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1500,
            stream=True,
        )

        demand_letter = ""
        for chunk in stream:
            tok = chunk.choices[0].delta.content or ""
            if tok:
                demand_letter += tok
                _token("legal_agent", tok)

        _think("legal_agent", f"Letter complete — {len(demand_letter):,} characters")

    except Exception as e:
        demand_letter = f"[Demand letter generation failed: {e}]"
        _think("legal_agent", f"⚠ Error: {e}")

    return {"demand_letter": demand_letter}
