# PI Case Valuation Engine 
🔗 **[Live Demo](https://pi-settlement-valuation.vercel.app/)**
> **Intelligent personal-injury case analysis powered by a 4-node LangGraph multi-agent pipeline and Groq's free LLM tier.**
> Upload a medical record → watch every reasoning step in real time → receive an ICD-coded injury timeline, a three-tier settlement estimate, comparable case law, and a download-ready demand letter (PDF / Word / TXT).

---

## ⚠️ Legal Disclaimer

**This tool is for informational and educational purposes only. It does not constitute legal advice, create an attorney-client relationship, or replace the judgment of a licensed attorney. Settlement estimates are algorithmic approximations based on public damages formulas and should not be relied upon as predictions of actual case outcomes. Always consult a qualified personal-injury attorney before making any legal decisions.**

---

## Contents

1. [What it does](#what-it-does)
2. [Live demo architecture](#live-demo-architecture)
3. [Full capabilities](#full-capabilities)
4. [Pipeline — step by step](#pipeline--step-by-step)
5. [Context engineering](#context-engineering)
6. [MCP server](#mcp-server)
7. [APIs used](#apis-used)
8. [Tech stack](#tech-stack)
9. [Project structure](#project-structure)
10. [Local development](#local-development)
11. [Deploying to production](#deploying-to-production)
12. [Environment variables](#environment-variables)
13. [Sample test input](#sample-test-input)
14. [Free-tier limits](#free-tier-limits)

---

## What it does

A personal-injury attorney or paralegal uploads a medical record (PDF or pasted text). The system:

1. **Extracts** every injury event, diagnosis, treatment, and financial figure from free-form clinical notes using an LLM.
2. **Codes** each diagnosis with an ICD-10-CM code via the NLM Clinical Tables API.
3. **Scores** each diagnosis with an AIS (Abbreviated Injury Scale) severity level via a static medical reference table.
4. **Auto-parses** lost-wages and future-care estimates directly from the narrative text.
5. **Calculates** a three-tier settlement range (conservative / mid-range / high-end) using the Sacramento County PI damages formula with per-state jurisdiction adjustments.
6. **Searches** CourtListener for relevant case law opinions from real courts.
7. **Drafts** a professional demand letter ready to edit and send.
8. **Streams** every reasoning step — thoughts, LLM tokens, API calls — live in the browser as the pipeline runs.
9. **Exports** the demand letter as PDF, Word (.docx), or plain text, all generated client-side.
10. **Exposes all tools** via a hosted MCP server so any MCP-compatible AI client (Claude Desktop, Cursor Agent) can invoke the pipeline without touching the web UI.

---

## Live demo architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BROWSER  (Vercel)                            │
│                                                                     │
│  React + Vite                                                       │
│  ┌───────────────┐   upload / text   ┌──────────────────────────┐  │
│  │  UploadPanel  │ ────────────────► │  useCaseAnalysis hook    │  │
│  └───────────────┘                   │  fetch POST /analyze/    │  │
│                                      │        stream  (SSE)     │  │
│  ┌───────────────────────────────┐   └────────────┬─────────────┘  │
│  │  PipelineProgress             │                │ SSE events      │
│  │  ① 🔬 Medical Extraction      │ ◄──────────────┤ thought/token/  │
│  │  ② 🏥 ICD-10 + AIS Coding     │                │ node/done       │
│  │  ③ ⚖️  Damages Calculation     │                │                 │
│  │  ④ 📝 Demand Letter           │                │                 │
│  └───────────────────────────────┘                │                 │
│                                                   │                 │
│  ┌──────────────────────────────────────────────┐ │                 │
│  │  Result Cards                                │ │                 │
│  │  InjuryTimeline · SeverityScorecard          │ │                 │
│  │  ValuationReport · CaseOpinions              │ │                 │
│  │  DemandLetter (PDF / Word / .txt download)   │ │                 │
│  └──────────────────────────────────────────────┘ │                 │
└───────────────────────────────────────────────────┼─────────────────┘
                                                    │
                          HTTPS                     │
                                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                      RAILWAY  (FastAPI backend)                        │
│                                                                        │
│  POST /analyze/stream  ──►  background thread                         │
│  POST /analyze         ──►  pipeline.invoke()  (sync, for MCP)        │
│  GET  /health                                                          │
│                                                                        │
│  /mcp/*  ──►  FastMCP (Streamable HTTP)                               │
│               5 tools: analyze · search_icd · procedure_cost ·        │
│                         settlement_range · drug_reactions              │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  LangGraph pipeline  (compiled StateGraph)                       │ │
│  │                                                                  │ │
│  │  START → medical_agent ──(retry≤2)──► icd_agent                 │ │
│  │            │ ↑ retry                       │                    │ │
│  │            └──────────────────────         ▼                    │ │
│  │                                      damages_agent              │ │
│  │                                            │                    │ │
│  │                                            ▼                    │ │
│  │                                       legal_agent → END         │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  External API calls (all free):                                       │
│  NLM ICD-10  ·  CourtListener  ·  OpenFDA  ·  CMS Fee Schedule       │
│                                                                        │
│  LLM calls (Groq free tier):                                          │
│  medical_agent → llama-3.3-70b-versatile  (extraction, streaming)    │
│  legal_agent   → llama-3.3-70b-versatile  (demand letter, streaming) │
└───────────────────────────────────────────────────────────────────────┘
                                    ▲
                  MCP JSON-RPC      │
                                    │
┌────────────────────────────────┐  │
│  AI Client                     │  │
│  (Claude Desktop / Cursor)     │──┘
│  calls tools via MCP protocol  │
└────────────────────────────────┘
```

---

## Full capabilities

### Analysis pipeline
| Capability | Detail |
|---|---|
| PDF ingestion | `pdfplumber` extracts text from multi-page PDFs client-side on the server |
| Free-text ingestion | Paste raw clinical notes, ER reports, discharge summaries |
| Injury extraction | LLM returns structured JSON: event type, description, body part, date, severity, permanence, billed cost |
| Financial auto-parse | LLM parses `"6 weeks @ $1,200/week"` → `$7,200` lost wages; `"Estimated cost: $35,000"` → future care |
| ICD-10-CM coding | Per-diagnosis lookup via NLM Clinical Tables API (live, verified codes) |
| AIS severity scoring | Static medical reference table: AIS 1 (Minor) → AIS 6 (Unsurvivable) |
| Settlement calculation | Sacramento County formula · economic + non-economic with multiplier · 3-tier output |
| Jurisdiction adjustment | State factors for CA, NY, TX, FL, IL (configurable) |
| Case law search | CourtListener API: top 3 relevant opinions with name, court, date, snippet, link |
| Demand letter | LLM-drafted professional legal letter with injuries narrative + damages table |
| Demand letter export | Client-side PDF (jsPDF, US Letter, Times New Roman, page numbers), Word (.docx, 1.25" margins, bold headings), plain text |

### Live pipeline visualisation
| Feature | Detail |
|---|---|
| Step-by-step progress | 4 steps light up sequentially with spinner → green ✓ |
| Thought log | Per-step reasoning entries slide in as they arrive |
| LLM token streaming | Raw Groq output streams character-by-character (medical JSON + demand letter) |
| Timing | Each step shows elapsed time when complete |
| Output previews | Medical: injury chips + severity tags; ICD: code + AIS badge table; Damages: 3-tier range boxes; Legal: letter preview quote |
| Collapsible reasoning | After each step completes, "▼ Show chain of thought" reveals the full log |

### MCP server (AI client integration)
| Tool | What it does |
|---|---|
| `analyze_medical_record` | Full pipeline: text → injuries + valuation + opinions + demand letter |
| `search_icd_codes` | NLM ICD-10 lookup by plain-language description (7 results) |
| `get_procedure_cost` | CMS Physician Fee Schedule: Medicare payment rates for procedures |
| `calculate_settlement_range` | Pure-math settlement estimate from raw damage inputs |
| `lookup_drug_reactions` | OpenFDA FAERS: adverse reactions for medications in record |

---

## Pipeline — step by step

### Node 1 — Medical Extraction (`medical_agent`)
- **LLM call:** 1 streaming Groq call (`llama-3.3-70b-versatile`, temp 0.1, max 2000 tokens)
- **Input:** raw text (truncated to 12,000 chars)
- **Output:** `injuries[]` — structured array of all events + `parsed_lost_wages`, `parsed_future_care`
- **Retry logic:** if the LLM returns an empty list, retries up to 2× before continuing

**Thought log emits:** record size → prompt build → "Querying Groq [streaming]" → raw JSON tokens → "Extracted N events" → billed total → auto-parsed financials → severity breakdown

### Node 2 — ICD-10 + AIS Coding (`icd_agent`)
- **No LLM.** Direct NLM Clinical Tables API call per diagnosis + static AIS lookup table
- **Input:** `injuries[]` from node 1
- **Output:** same array enriched with `icd_code`, `ais_score`, `ais_label` per diagnosis

**Thought log emits:** per-diagnosis NLM query + result code → AIS assignment per diagnosis

### Node 3 — Damages Calculation (`damages_agent`)
- **No LLM.** Pure Python math + CourtListener API call
- **Input:** enriched `injuries[]`, jurisdiction, lost_wages, future_care
- **Output:** `valuation{}` (conservative / mid-range / high-end / multiplier / economic breakdown) + `case_opinions[]`
- **Fallback:** if user leaves wages/care at 0, uses `parsed_lost_wages` / `parsed_future_care` from node 1

**Thought log emits:** jurisdiction → per-line damages breakdown → multiplier logic → all 3 estimates → CourtListener query + returned cases

**Settlement formula:**
```
medical_specials  = sum of all past billed costs
economic          = medical_specials + lost_wages + future_care
non_economic      = medical_specials × multiplier  (AIS-based, 1.5× – 4.5×)
base              = economic + non_economic
conservative      = base × 0.70 × jurisdiction_factor
mid_range         = base × 1.00 × jurisdiction_factor
high_end          = base × 1.40 × jurisdiction_factor
```

**AIS → multiplier table:**
| Max AIS | Multiplier |
|---|---|
| 1 (Minor) | 1.5× |
| 2 (Moderate) | 2.5× |
| 3 (Serious) | 3.0× |
| 4 (Severe) | 4.0× |
| 5+ or Permanent | 4.5× |

### Node 4 — Demand Letter (`legal_agent`)
- **LLM call:** 1 streaming Groq call (`llama-3.3-70b-versatile`, temp 0.4, max 1500 tokens)
- **Input:** coded injuries + full valuation dict
- **Output:** `demand_letter` — formatted letter with injuries narrative, damages table, and settlement demand

**Thought log emits:** injury count → total demand → "Querying Groq [streaming]" → letter tokens → char count

---

## Context engineering

Context engineering is the practice of deliberately shaping *what goes into the LLM's context window* — not just the prompt wording, but which information is present, in what order, and at what density. This project applies five concrete techniques across its two LLM calls.

---

### Technique 1 — Boilerplate compression (`_compress_medical_record`)

**Problem:** Real medical records are 30–50% noise — HIPAA notices, page headers, separator lines, address blocks, and irrelevant section boilerplate.

**Solution:** Before sending any text to the LLM, `_compress_medical_record()` strips:
- HIPAA/confidentiality notice lines (regex matched)
- Page numbers and `"Printed by / Generated on"` footers
- Separator lines (`----`, `====`, `****`)
- Consecutive blank lines (collapsed to one)
- Entire low-value sections: **MEDICATIONS LIST**, **FAMILY HISTORY**, **SOCIAL HISTORY**, **IMMUNIZATIONS**, **ALLERGY LIST**, **REVIEW OF SYSTEMS** — none of which matter for PI valuation

**Result:** The LLM receives a record that is 20–40% shorter with the same clinical signal, reducing token cost and improving extraction accuracy.

---

### Technique 2 — Dynamic context selection (`_select_context`)

**Problem:** A hard character slice is naive — it cuts mid-sentence on long records and wastes tokens on very short ones.

**Solution:** `_select_context()` applies a three-tier strategy based on record length after compression:

| Record length (after compression) | Strategy | What the LLM receives |
|---|---|---|
| ≤ 4,000 chars | **Full text** | Entire record unchanged |
| ≤ 8,000 chars | **Compress only** | Boilerplate stripped, full clinical content |
| > 8,000 chars | **Smart section extract** | Only PI-relevant sections, up to 6,000 chars |

The thought log in the UI shows which strategy was applied and the exact character counts at each stage (e.g. `"Context strategy: section-extracted (18,240 → 11,100 → 5,980 chars)"`).

---

### Technique 3 — Smart section extraction (`_smart_section_extract`)

**Problem:** Long records have many sections; only a subset matters for PI analysis.

**Solution:** For records that are still long after compression, `_smart_section_extract()` parses the document into sections by detecting all-caps headers, then scores each section:

**Priority sections (always included first):**
`ASSESSMENT` · `IMPRESSION` · `DIAGNOSES` · `HPI` · `CHIEF COMPLAINT` · `PLAN` · `TREATMENT` · `SURGERY` · `RADIOLOGY` · `MRI` · `IMAGING` · `BILLING` · `CHARGES` · `PROGNOSIS` · `DISCHARGE SUMMARY`

**Low-priority sections** (filled in only if space remains up to 6,000 chars): subjective findings, nursing notes, vital signs, etc.

Token usage stays flat at ≈6,000 chars regardless of how long the original PDF was.

---

### Technique 4 — Few-shot example in extraction prompt

**Problem:** Even with a clear schema, LLMs occasionally produce malformed JSON, wrong field names, or markdown-fenced responses.

**Solution:** A single worked example is embedded directly in the `EXTRACT_SYSTEM` prompt between `--- EXAMPLE ---` delimiters, showing a short clinical note mapped to the exact expected JSON output with correct field names and number parsing. The LLM mirrors the demonstrated format without re-inferring the schema, eliminating virtually all JSON parse errors on the first attempt.

---

### Technique 5 — Case law context injection into demand letter

**Problem:** The demand letter was generated purely from injury data and damages numbers — with no awareness of how courts in the same jurisdiction have ruled on similar cases.

**Solution:** After `damages_agent` retrieves opinions from CourtListener, `legal_agent` now receives them in its prompt under a `RELEVANT CASE LAW` block. The LLM references these naturally in the letter body, producing a demand letter that cites real precedent. If CourtListener returns nothing, the block is absent and the letter generates as before — zero risk of breakage.

---

### Summary

| # | Technique | Where applied | Benefit |
|---|---|---|---|
| 1 | Boilerplate compression | Before `medical_agent` LLM call | 20–40% fewer tokens, cleaner extraction |
| 2 | Dynamic context selection | Before `medical_agent` LLM call | Flat token cost regardless of PDF length |
| 3 | Smart section extraction | Before `medical_agent` LLM call (long records) | Only PI-relevant sections reach the LLM |
| 4 | Few-shot example in system prompt | `medical_agent` system prompt | Near-zero JSON parse errors |
| 5 | Case law context injection | `legal_agent` prompt | Demand letters cite real court precedent |

---

## MCP server

### Do you need to start it manually?

**No.** The MCP server starts automatically as part of the FastAPI backend. There is no separate process, no extra port, and no extra command. When uvicorn starts `main.py`, the MCP server is mounted at `/mcp` and is immediately ready.

```
# Local
http://localhost:8000/mcp

# Production (Railway)
https://your-railway-app.railway.app/mcp
```

The MCP protocol is open and free — it costs nothing to use. All LLM inference happens via **your Groq key on your Railway server**, so there is no additional Claude/OpenAI cost regardless of which AI client connects.

---

### What the MCP server exposes

Five tools are available to any MCP-compatible client:

| Tool | Description |
|---|---|
| `analyze_medical_record` | **Full pipeline** — text in, everything out (injuries, ICD codes, AIS scores, settlement range, case law, demand letter) |
| `search_icd_codes` | Look up ICD-10-CM codes by plain-language description |
| `get_procedure_cost` | Medicare payment rates for procedures (CMS fee schedule) |
| `calculate_settlement_range` | Settlement math from raw numbers (specials, wages, future care, AIS) |
| `lookup_drug_reactions` | Adverse drug reactions from OpenFDA FAERS database |

---

### Connecting from Claude Desktop

1. Open (or create) the Claude Desktop config file:
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

2. Add the server entry:

```json
{
  "mcpServers": {
    "pi-valuation": {
      "type": "http",
      "url": "https://your-railway-app.railway.app/mcp"
    }
  }
}
```

3. Restart Claude Desktop. A hammer icon will appear in the bottom-left of the chat input — that shows MCP tools are connected.

**Testing it:** paste a medical record into Claude and ask:
> *"Analyze this medical record and give me a full PI case valuation with a demand letter."*

Claude will call `analyze_medical_record`, get back the full structured result, and summarise it for you in natural language.

---

### Connecting from Claude Desktop (local backend)

If you are running the backend on your own machine (`localhost:8000`) and want to use it from Claude Desktop without deploying to Railway:

```json
{
  "mcpServers": {
    "pi-valuation-local": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

The backend must be running (`uvicorn main:app --reload --port 8000`) whenever Claude Desktop starts. Claude connects to it locally — nothing leaves your machine except the Groq API call.

---

### Connecting from Cursor (Agent mode)

1. Open your project in Cursor
2. Create or edit `.cursor/mcp.json` in the workspace root:

```json
{
  "mcpServers": {
    "pi-valuation": {
      "type": "http",
      "url": "https://your-railway-app.railway.app/mcp"
    }
  }
}
```

3. Open the Cursor chat panel, switch to **Agent** mode
4. You will see the 5 tools listed under the MCP section

**Example prompts in Cursor Agent:**
> *"Use the pi-valuation tool to search ICD-10 codes for 'herniated disc with radiculopathy'"*

> *"Calculate a settlement range: $14,000 specials, $7,200 lost wages, $35,000 future care, AIS 3, permanent injury, California"*

> *"Analyze this medical record text and generate a demand letter"* ← then paste the record

---

### Calling MCP tools with any HTTP client (curl / Postman)

MCP Streamable HTTP uses JSON-RPC 2.0. You can call it directly:

```bash
# List available tools
curl -X POST https://your-railway-app.railway.app/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Call search_icd_codes
curl -X POST https://your-railway-app.railway.app/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_icd_codes",
      "arguments": { "description": "cervical disc herniation" }
    }
  }'
```

---

### MCP vs REST API — which to use?

| | REST (`/analyze/stream`) | MCP (`/mcp`) |
|---|---|---|
| Best for | Human using the web UI | AI agent incorporating PI analysis into a larger task |
| Protocol | SSE over HTTP | JSON-RPC over HTTP (MCP spec) |
| Streaming | Yes — tokens + thoughts live | No — blocks until complete, returns JSON |
| Auth | None (add your own) | None (add your own) |
| Same pipeline? | Yes | Yes |

---

## APIs used

All APIs are **free** with no credit card required (optional API keys only raise rate limits).

| API | Purpose | Auth | Rate limit |
|---|---|---|---|
| [Groq](https://console.groq.com) | LLM inference (Llama 3.3 70B) | API key (free) | 14,400 tokens/min · 100 req/day free |
| [NLM Clinical Tables](https://clinicaltables.nlm.nih.gov/) | ICD-10-CM code search and validation | None | Generous, no key needed |
| [CourtListener](https://www.courtlistener.com/help/api/) | Legal case opinion search | Token (free, [sign up](https://www.courtlistener.com/sign-in/)) | 5,000 req/day with free token |
| [OpenFDA FAERS](https://open.fda.gov/apis/) | Adverse drug reaction lookup | Optional key ([get one](https://open.fda.gov/apis/authentication/)) | 240 req/min (key), 40/min (no key) |
| [CMS Physician Fee Schedule](https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners/medicare-physician-other-practitioners-by-provider-and-service) | Medicare procedure payment rates | None | Public Socrata API, no limit |

### NLM Clinical Tables — ICD-10-CM

```
GET https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search
    ?sf=code,name&df=code,name&terms=cervical+disc+herniation&maxList=7
```
Returns a ranked list of matching ICD-10-CM codes with full names. Used in `icd_agent_node` and the `search_icd_codes` MCP tool. No registration, no key, no rate limit documented.

### CourtListener

```
GET https://www.courtlistener.com/api/rest/v4/search/
    ?q=cervical+disc+herniation+personal+injury+CA&type=o&$limit=3
Authorization: Token <your_token>
```
Returns real court opinions with case name, date filed, court, snippet, and URL. Used in `damages_agent_node`. Works without a token (anonymous) at lower limits.

### OpenFDA FAERS

```
GET https://api.fda.gov/drug/event.json
    ?search=patient.drug.medicinalproduct:"oxycodone"&limit=3
```
Returns adverse drug events from the FDA Adverse Event Reporting System. Used in the `lookup_drug_reactions` MCP tool. Optional key raises rate limits.

### CMS Physician Fee Schedule

```
GET https://data.cms.gov/resource/6pcd-ht5d.json
    ?$q=ACDF+cervical+fusion&$limit=1
```
Returns Medicare national and facility payment rates by HCPCS procedure code. Used in the `get_procedure_cost` MCP tool.

---

## Tech stack

### Backend
| Component | Library / Service | Version |
|---|---|---|
| API framework | FastAPI | latest |
| ASGI server | Uvicorn | latest |
| Multi-agent orchestration | LangGraph | ≥0.2.0 |
| LLM client | Groq Python SDK | latest |
| LangChain integration | langchain-groq | ≥0.2.0 |
| MCP server | FastMCP (`mcp[cli]`) | ≥1.0.0 |
| HTTP client | httpx | ≥0.27.0 |
| PDF text extraction | pdfplumber | latest |
| Environment config | python-dotenv | latest |
| Form file uploads | python-multipart | latest |

### Frontend
| Component | Library | Version |
|---|---|---|
| UI framework | React | 18.3 |
| Build tool | Vite | 6.x |
| File drag-and-drop | react-dropzone | 14.x |
| HTTP client | axios | 1.7 |
| Icons | lucide-react | 0.468 |
| PDF generation | jsPDF | 4.x |
| Word (.docx) generation | docx | 9.x |

### Infrastructure
| Layer | Platform | Notes |
|---|---|---|
| Frontend hosting | [Vercel](https://vercel.com) | Free tier, auto-deploy from GitHub |
| Backend hosting | [Railway](https://railway.app) | Free trial, $5/mo hobby plan after |
| LLM inference | [Groq](https://groq.com) | Free tier: 14,400 tokens/min |

---

## Project structure

```
pi-valuation/
├── backend/
│   ├── main.py                  # FastAPI app, /analyze, /analyze/stream, mounts /mcp
│   ├── mcp_server.py            # FastMCP server — 5 tools
│   ├── requirements.txt
│   ├── Procfile                 # Railway start command
│   ├── railway.json             # Railway build config (Nixpacks)
│   ├── .env                     # Local secrets (not committed)
│   ├── .env.example             # Template for env vars
│   │
│   ├── graph/
│   │   ├── graph.py             # LangGraph StateGraph definition + compiled pipeline
│   │   ├── state.py             # CaseState TypedDict
│   │   ├── nodes.py             # 4 agent nodes + _think/_token side channel
│   │   └── tools/
│   │       ├── medical_tools.py # PDF parse + Groq extraction tool wrappers
│   │       ├── coding_tools.py  # ICD-10 + AIS tool wrappers
│   │       ├── damages_tools.py # Settlement calc + CourtListener tool wrappers
│   │       └── legal_tools.py   # Demand letter tool wrapper
│   │
│   └── services/
│       ├── parser.py            # PDF → text (pdfplumber)
│       ├── extractor.py         # Text → injury events (Groq)
│       ├── icd_predictor.py     # Injury description → ICD code
│       ├── ais_mapper.py        # ICD code → AIS score (static table)
│       ├── valuation.py         # Settlement range math
│       └── demand_letter.py     # Demand letter generation
│
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── vercel.json              # Vercel SPA routing config
    ├── package.json
    │
    └── src/
        ├── App.jsx              # Root component, result layout
        ├── App.css              # Full design system (dark theme)
        ├── main.jsx
        │
        ├── hooks/
        │   └── useCaseAnalysis.js  # SSE streaming hook, token batching
        │
        └── components/
            ├── UploadPanel.jsx      # File dropzone + text input + form fields
            ├── PipelineProgress.jsx # Live 4-step pipeline visualiser + thought log
            ├── InjuryTimeline.jsx   # Chronological injury event cards
            ├── SeverityScorecard.jsx # AIS gauge + injury severity breakdown
            ├── ValuationReport.jsx  # Settlement range bars + damages table
            ├── CaseOpinions.jsx     # CourtListener case law cards
            └── DemandLetter.jsx     # Letter viewer + PDF/Word/.txt export
```

---

## Local development

### Prerequisites
- Python 3.10+
- Node.js 18+
- A free [Groq API key](https://console.groq.com)

### 1. Clone the repo

```bash
git clone https://github.com/Shashwat-Jha06/pi-settlement-valuation.git
cd pi-settlement-valuation
```

### 2. Backend setup

```powershell
cd backend

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate          # Windows
# source venv/bin/activate       # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Configure secrets
copy .env.example .env
# Edit .env and set GROQ_API_KEY=gsk_...
```

### 3. Frontend setup

```powershell
cd ..\frontend
npm install
```

### 4. Run locally

Open **two terminals**:

```powershell
# Terminal 1 — Backend
cd backend
.\venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

```powershell
# Terminal 2 — Frontend
cd frontend
npm run dev
```

Open **http://localhost:5173**

### Optional API keys (improve results)

```env
# backend/.env
COURTLISTENER_TOKEN=your_token   # courtlistener.com/sign-in/ — free, raises daily limit
OPENFDA_API_KEY=your_key         # open.fda.gov — free, raises rate limit
```

---

## Deploying to production

### Backend → Railway

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Select the repo, set **Root Directory** to `pi-valuation/backend`
4. Add environment variables in Railway's dashboard:

| Variable | Value |
|---|---|
| `GROQ_API_KEY` | `gsk_...` |
| `COURTLISTENER_TOKEN` | *(optional)* |
| `OPENFDA_API_KEY` | *(optional)* |
| `FRONTEND_URL` | `https://your-app.vercel.app` |

5. Railway uses `Procfile` automatically: `web: uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Note your Railway URL: `https://your-app.railway.app`

### Frontend → Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project** → import GitHub repo
2. Set **Root Directory** to `pi-valuation/frontend`
3. Add environment variable:

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://your-app.railway.app` |

4. Deploy — Vercel detects Vite automatically
5. `vercel.json` handles SPA routing

### MCP endpoint (auto-deployed with backend)

No extra steps. Once Railway is running, your MCP server is live at:
```
https://your-app.railway.app/mcp
```

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | **Yes** | Groq API key from [console.groq.com](https://console.groq.com) |
| `COURTLISTENER_TOKEN` | No | Free token from [courtlistener.com](https://www.courtlistener.com/sign-in/) — increases daily limit to 5,000 req/day |
| `OPENFDA_API_KEY` | No | Free key from [open.fda.gov](https://open.fda.gov/apis/authentication/) — increases rate limit from 40 to 240 req/min |
| `FRONTEND_URL` | Production | Your Vercel URL — added to CORS allowlist |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | Production | Your Railway backend URL, e.g. `https://your-app.railway.app` |

---

## Sample test input

Paste this into the **Paste Text** tab to test the full pipeline:

```
Patient: [REDACTED] | Date of Injury: January 3, 2024

HPI: 34-year-old male presents following MVA on 01/03/2024.
Reports severe neck pain and radiating left arm numbness since accident.

MRI cervical spine (01/10/2024): Herniated disc C4-C5 with moderate
left foraminal stenosis. Billed: $3,200.
ER visit 01/03/2024: Billed $8,400.
Physical therapy 02/01/2024 – 04/01/2024: 12 sessions @ $200/session = $2,400.
Neurology consult 04/15/2024: Permanent left arm radiculopathy confirmed.
Surgical consult: Likely ACDF surgery recommended. Estimated cost: $35,000.

Diagnoses:
- Cervical disc herniation M50.12
- Permanent left C5 radiculopathy M54.12

Lost work: 6 weeks @ $1,200/week = $7,200.
```

**Expected outputs:**
- 5–7 injury events extracted
- ICD codes: M50.12, M54.12
- AIS scores: 2 (Moderate)
- Auto-parsed: lost wages $7,200, future care $35,000
- Multiplier: ~3.0–3.5 (permanent injury)
- Mid-range estimate: ~$150,000–$220,000
- 3 CourtListener opinions returned
- Full demand letter drafted

---

## Free-tier limits

| Resource | Free limit | Per-analysis usage | Max analyses/day |
|---|---|---|---|
| Groq tokens | 14,400 / min · 500,000 / day | ~3,000–5,000 tokens (2 LLM calls) | ~100–160 |
| Groq requests | 100 req/day (free tier) | 2 requests | **50 analyses/day** |
| NLM ICD-10 | Unlimited | 1–3 calls | Unlimited |
| CourtListener | 5,000 req/day (with token) | 1 call | 5,000 |
| OpenFDA | 240 req/min (with key) | 0–1 call (MCP only) | Unlimited |
| CMS Fee Schedule | Unlimited | 0–1 call (MCP only) | Unlimited |

> **Tip:** Groq's free tier is the binding constraint. If you need higher throughput, Groq's paid tier starts at $0.59/million tokens — a full analysis costs less than $0.003.

---

## Contributing

Pull requests welcome. Key areas for improvement:
- Add more jurisdiction-specific damages formulas
- Improve AIS mapping coverage (currently ~150 ICD-10 patterns)
- Add structured output for the demand letter (replace plain text with sectioned JSON)
- Add a case intake form (plaintiff info, accident details) to pre-populate the letter placeholders

---

*Built with [Groq](https://groq.com) · [LangGraph](https://github.com/langchain-ai/langgraph) · [FastAPI](https://fastapi.tiangolo.com) · [React](https://react.dev)*
