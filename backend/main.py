import os
import json
import queue as _queue_mod
import threading
import traceback
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from services.parser import extract_text_from_pdf

load_dotenv()

app = FastAPI(title="PI Case Valuation Engine")

# ── CORS ──────────────────────────────────────────────────────────────────────
_origins = ["http://localhost:5173", "http://localhost:3000"]
_frontend_url = os.environ.get("FRONTEND_URL", "")
if _frontend_url:
    _origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"http://localhost:\d+",   # covers any Vite port in dev
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount MCP server at /mcp ──────────────────────────────────────────────────
from mcp_server import create_mcp_app
app.mount("/mcp", create_mcp_app())


# ── REST Endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_case(
    file: UploadFile = File(None),
    raw_text: str = Form(None),
    jurisdiction: str = Form("CA"),
    lost_wages: float = Form(0),
    future_care: float = Form(0),
):
    try:
        if file and file.filename:
            text = extract_text_from_pdf(await file.read())
        elif raw_text:
            text = raw_text
        else:
            raise HTTPException(status_code=400, detail="Provide either a PDF file or raw_text.")

        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Could not extract any text.")

        from graph.graph import pipeline

        result = pipeline.invoke({
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
        })

        return {
            "injuries": result.get("injuries", []),
            "valuation": result.get("valuation", {}),
            "case_opinions": result.get("case_opinions", []),
            "demand_letter": result.get("demand_letter", ""),
            "parsed_lost_wages": result.get("parsed_lost_wages", 0),
            "parsed_future_care": result.get("parsed_future_care", 0),
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Streaming / SSE endpoint ─────────────────────────────────────────────────

def _make_initial_state(text: str, jurisdiction: str, lost_wages: float, future_care: float):
    return {
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


def _summary_for_progress(node_name: str, output: dict) -> dict:
    """Compact summary for the PipelineProgress step cards."""
    if node_name == "medical_agent":
        injuries = output.get("injuries", [])
        total_billed = sum(i.get("medical_cost_billed", 0) or 0 for i in injuries)
        return {
            "injuries_count": len(injuries),
            "total_billed": total_billed,
            "parsed_lost_wages": output.get("parsed_lost_wages", 0),
            "parsed_future_care": output.get("parsed_future_care", 0),
            "sample_injuries": [
                {"description": i.get("description", ""), "severity_indicator": i.get("severity_indicator", "")}
                for i in injuries[:4]
            ],
        }
    if node_name == "icd_agent":
        injuries = output.get("injuries", [])
        diagnoses = [
            {
                "description": i.get("description", ""),
                "icd_code": i.get("icd_code", ""),
                "ais_score": i.get("ais_score"),
                "ais_label": i.get("ais_label", ""),
            }
            for i in injuries if i.get("event_type") == "diagnosis"
        ]
        return {"diagnoses": diagnoses, "total_events": len(injuries)}
    if node_name == "damages_agent":
        val = output.get("valuation", {})
        return {
            "conservative": val.get("conservative", 0),
            "mid_range": val.get("mid_range", 0),
            "high_end": val.get("high_end", 0),
            "multiplier": val.get("multiplier", 0),
            "medical_specials": val.get("medical_specials", 0),
            "case_opinions_count": len(output.get("case_opinions", [])),
        }
    if node_name == "legal_agent":
        letter = output.get("demand_letter", "")
        return {
            "letter_preview": letter[:200],
            "letter_length": len(letter),
        }
    return {}


def _data_for_results(node_name: str, output: dict) -> dict:
    """Full data for progressive result card rendering on the frontend."""
    if node_name == "medical_agent":
        return {
            "injuries": output.get("injuries", []),
            "parsed_lost_wages": output.get("parsed_lost_wages", 0),
            "parsed_future_care": output.get("parsed_future_care", 0),
        }
    if node_name == "icd_agent":
        return {"injuries": output.get("injuries", [])}
    if node_name == "damages_agent":
        return {
            "valuation": output.get("valuation", {}),
            "case_opinions": output.get("case_opinions", []),
        }
    if node_name == "legal_agent":
        return {"demand_letter": output.get("demand_letter", "")}
    return {}


@app.post("/analyze/stream")
async def analyze_case_stream(
    file: UploadFile = File(None),
    raw_text: str = Form(None),
    jurisdiction: str = Form("CA"),
    lost_wages: float = Form(0),
    future_care: float = Form(0),
):
    # Extract text before entering async generator (file read must be awaited)
    if file and file.filename:
        text = extract_text_from_pdf(await file.read())
    elif raw_text:
        text = raw_text
    else:
        raise HTTPException(status_code=400, detail="Provide either a PDF file or raw_text.")

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract any text.")

    from graph.graph import pipeline
    initial_state = _make_initial_state(text, jurisdiction, lost_wages, future_care)

    async def event_generator():
        # Single merged queue — both pipeline node events AND thought/token
        # events from nodes._thought_queues flow through here so the generator
        # can interleave them naturally in emission order.
        merged_q: _queue_mod.Queue = _queue_mod.Queue()

        def run_pipeline():
            import graph.nodes as _nodes
            tid = threading.current_thread().ident
            _nodes._thought_queues[tid] = merged_q
            try:
                for event in pipeline.stream(initial_state, stream_mode="updates"):
                    merged_q.put(("event", event))
                merged_q.put(("done", None))
            except Exception as exc:
                merged_q.put(("error", str(exc)))
            finally:
                _nodes._thought_queues.pop(tid, None)

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        import asyncio
        accumulated = {}  # build up full result across node updates

        while True:
            try:
                kind, data = merged_q.get_nowait()
            except _queue_mod.Empty:
                await asyncio.sleep(0.01)   # tight poll — tokens need low latency
                continue

            # ── Thought / token events from nodes (emitted as-is) ────────────
            if kind == "thought":
                yield f"data: {json.dumps(data)}\n\n"
                continue

            # ── Pipeline error ────────────────────────────────────────────────
            if kind == "error":
                payload = json.dumps({"node": "error", "output": {"message": data}})
                yield f"data: {payload}\n\n"
                break

            # ── Pipeline complete ─────────────────────────────────────────────
            if kind == "done":
                final = json.dumps({"node": "done", "output": accumulated}, default=str)
                yield f"data: {final}\n\n"
                break

            # ── Node completion event ─────────────────────────────────────────
            node_name = list(data.keys())[0] if data else "unknown"
            node_output = data.get(node_name, {})
            accumulated.update(node_output)

            payload = json.dumps({
                "node": node_name,
                "output": _summary_for_progress(node_name, node_output),  # for PipelineProgress
                "data":   _data_for_results(node_name, node_output),      # for result cards
            })
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
