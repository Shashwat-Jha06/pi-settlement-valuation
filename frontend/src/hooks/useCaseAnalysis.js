import { useState, useCallback, useRef } from "react"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000"

export const PIPELINE_STEPS = [
  {
    id: "medical_agent",
    label: "Medical Extraction",
    icon: "🔬",
    description: "Extracting injuries, diagnoses & financials from record",
  },
  {
    id: "icd_agent",
    label: "ICD-10 + AIS Coding",
    icon: "🏥",
    description: "Assigning ICD-10 codes and AIS severity scores via NLM API",
  },
  {
    id: "damages_agent",
    label: "Damages Calculation",
    icon: "⚖️",
    description: "Computing settlement range and searching case law",
  },
  {
    id: "legal_agent",
    label: "Demand Letter",
    icon: "📝",
    description: "Drafting professional demand letter",
  },
]

function makeInitialSteps() {
  return PIPELINE_STEPS.map((s) => ({
    ...s,
    status: "waiting",
    output: null,
    elapsed: null,
    thoughts: [],   // [{message: string}]
    liveText: "",   // accumulating LLM tokens
  }))
}

export function useCaseAnalysis() {
  const [result, setResult] = useState(null)
  const [partialResult, setPartialResult] = useState(null)  // fills in as nodes complete
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [steps, setSteps] = useState(makeInitialSteps())

  // Token batching: buffer rapid token events and flush via requestAnimationFrame
  // to avoid triggering hundreds of React re-renders per second.
  const tokenBuf = useRef({})     // { stepId: string }
  const rafPending = useRef(false)

  const flushTokens = useCallback(() => {
    const snapshot = { ...tokenBuf.current }
    Object.keys(snapshot).forEach((k) => { tokenBuf.current[k] = "" })
    rafPending.current = false
    setSteps((prev) =>
      prev.map((s) => {
        const chunk = snapshot[s.id]
        return chunk ? { ...s, liveText: s.liveText + chunk } : s
      })
    )
  }, [])

  const appendToken = useCallback((stepId, tok) => {
    tokenBuf.current[stepId] = (tokenBuf.current[stepId] || "") + tok
    if (!rafPending.current) {
      rafPending.current = true
      requestAnimationFrame(flushTokens)
    }
  }, [flushTokens])

  const analyze = useCallback(
    async ({ file, rawText, jurisdiction, lostWages, futureCare }) => {
      setLoading(true)
      setError(null)
      setResult(null)
      setPartialResult(null)
      setSteps(makeInitialSteps())
      tokenBuf.current = {}
      rafPending.current = false

      const form = new FormData()
      if (file) form.append("file", file)
      if (rawText) form.append("raw_text", rawText)
      form.append("jurisdiction", jurisdiction || "CA")
      form.append("lost_wages", lostWages || 0)
      form.append("future_care", futureCare || 0)

      try {
        const res = await fetch(`${API_BASE}/analyze/stream`, {
          method: "POST",
          body: form,
        })

        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${res.status}`)
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ""

        // Track when each step first received an event, to compute elapsed time
        const startedAt = {}

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() // keep last incomplete line

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue
            const raw = line.slice(6).trim()
            if (!raw) continue

            let msg
            try { msg = JSON.parse(raw) } catch { continue }

            // ── LLM token (from Groq streaming) ─────────────────────────────
            if (msg.type === "token") {
              const stepId = msg.node
              if (!startedAt[stepId]) startedAt[stepId] = Date.now()
              // Mark step running on first token (in case no prior thought event)
              setSteps((prev) =>
                prev.map((s) =>
                  s.id === stepId && s.status === "waiting" ? { ...s, status: "running" } : s
                )
              )
              appendToken(stepId, msg.token)
              continue
            }

            // ── Thought log entry ────────────────────────────────────────────
            if (msg.type === "thought") {
              const stepId = msg.node
              if (!startedAt[stepId]) startedAt[stepId] = Date.now()
              setSteps((prev) =>
                prev.map((s) => {
                  if (s.id !== stepId) return s
                  return {
                    ...s,
                    status: s.status === "waiting" ? "running" : s.status,
                    thoughts: [...s.thoughts, { message: msg.message }],
                  }
                })
              )
              continue
            }

            // ── Pipeline done — full accumulated state ───────────────────────
            if (msg.node === "done") {
              const out = msg.output || {}
              setResult({
                injuries: out.injuries || [],
                valuation: out.valuation || {},
                case_opinions: out.case_opinions || [],
                demand_letter: out.demand_letter || "",
                parsed_lost_wages: out.parsed_lost_wages || 0,
                parsed_future_care: out.parsed_future_care || 0,
              })
              setLoading(false)
              return
            }

            // ── Pipeline error ───────────────────────────────────────────────
            if (msg.node === "error") {
              throw new Error(msg.output?.message || "Pipeline error")
            }

            // ── Node completion event ────────────────────────────────────────
            const { node, output, data: nodeData } = msg
            const stepIdx = PIPELINE_STEPS.findIndex((s) => s.id === node)
            if (stepIdx < 0) continue

            const elapsed = startedAt[node]
              ? ((Date.now() - startedAt[node]) / 1000).toFixed(1) + "s"
              : null

            // Update PipelineProgress step card
            setSteps((prev) =>
              prev.map((s) =>
                s.id === node ? { ...s, status: "done", output, elapsed } : s
              )
            )

            // Merge node's full data into partialResult for progressive card rendering
            if (nodeData) {
              setPartialResult((prev) => ({ ...(prev || {}), ...nodeData }))
            }
          }
        }
      } catch (e) {
        setError(e.message || "Analysis failed. Check your API key and try again.")
        setLoading(false)
      }
    },
    [appendToken]
  )

  return { analyze, result, partialResult, loading, error, steps }
}
