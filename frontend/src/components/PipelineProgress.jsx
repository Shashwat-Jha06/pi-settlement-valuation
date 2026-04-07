import { useEffect, useRef, useState } from "react"

export default function PipelineProgress({ steps }) {
  return (
    <div className="pipeline-card">
      <div className="pipeline-header">
        <span className="pipeline-title">Analysis Pipeline</span>
        <span className="pipeline-subtitle">LangGraph · 4 nodes · Groq llama-3.3-70b-versatile</span>
      </div>
      <div className="pipeline-steps">
        {steps.map((step, idx) => (
          <PipelineStep
            key={step.id}
            step={step}
            isLast={idx === steps.length - 1}
          />
        ))}
      </div>
    </div>
  )
}

// ── Individual Step ───────────────────────────────────────────────────────────

function PipelineStep({ step, isLast }) {
  const { status, label, icon, description, output, elapsed, thoughts, liveText } = step
  const [reasoningOpen, setReasoningOpen] = useState(false)

  const hasReasoning = thoughts.length > 0 || liveText.length > 0

  return (
    <div className={`pipeline-step pipeline-step--${status}`}>
      {/* Left connector */}
      <div className="step-connector">
        <div className="step-dot-wrap">
          <StepDot status={status} />
        </div>
        {!isLast && <div className={`step-line${status === "done" ? " step-line--done" : ""}`} />}
      </div>

      {/* Right content */}
      <div className="step-body">
        {/* Header row */}
        <div className="step-head">
          <span className="step-icon-emoji">{icon}</span>
          <span className="step-label">{label}</span>
          {status === "running" && <span className="step-running-badge">running…</span>}
          {status === "waiting" && <span className="step-waiting-badge">waiting</span>}
          {elapsed && <span className="step-elapsed">{elapsed}</span>}
        </div>

        {/* Waiting: description only */}
        {status === "waiting" && (
          <p className="step-description">{description}</p>
        )}

        {/* Running: live thoughts + streaming text */}
        {status === "running" && (
          <ThoughtsPanel thoughts={thoughts} liveText={liveText} stepId={step.id} alwaysOpen />
        )}

        {/* Done: output summary + collapsible reasoning */}
        {status === "done" && (
          <>
            {output && <StepOutput stepId={step.id} output={output} />}
            {hasReasoning && (
              <div className="reasoning-section">
                <button
                  className="reasoning-toggle-btn"
                  onClick={() => setReasoningOpen((v) => !v)}
                >
                  <span className="reasoning-toggle-icon">{reasoningOpen ? "▲" : "▼"}</span>
                  {reasoningOpen ? "Hide" : "Show"} chain of thought
                  <span className="reasoning-count">
                    {thoughts.length} step{thoughts.length !== 1 ? "s" : ""}
                    {liveText ? " + LLM output" : ""}
                  </span>
                </button>
                {reasoningOpen && (
                  <ThoughtsPanel thoughts={thoughts} liveText={liveText} stepId={step.id} />
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ── Dot icon ─────────────────────────────────────────────────────────────────

function StepDot({ status }) {
  if (status === "done")
    return <div className="step-dot step-dot--done">✓</div>
  if (status === "running")
    return (
      <div className="step-dot step-dot--running">
        <span className="spinner tiny" />
      </div>
    )
  return <div className="step-dot step-dot--waiting" />
}

// ── Thoughts panel (log + live text) ─────────────────────────────────────────

function ThoughtsPanel({ thoughts, liveText, stepId, alwaysOpen }) {
  const liveRef = useRef(null)

  // Auto-scroll the live text area to the bottom on every new token
  useEffect(() => {
    if (liveRef.current) {
      liveRef.current.scrollTop = liveRef.current.scrollHeight
    }
  }, [liveText])

  const isLLMStep = stepId === "medical_agent" || stepId === "legal_agent"
  const liveLabel =
    stepId === "legal_agent"
      ? "LLM Output · Demand Letter"
      : "LLM Output · Extraction JSON"

  return (
    <div className={`thoughts-panel${alwaysOpen ? " thoughts-panel--live" : ""}`}>
      {/* Thought log */}
      {thoughts.length > 0 && (
        <div className="thought-log">
          {thoughts.map((t, i) => (
            <div key={i} className="thought-entry">
              <span className="thought-bullet">›</span>
              <span className="thought-msg">{t.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Live / captured LLM stream */}
      {liveText && isLLMStep && (
        <div className="live-text-wrap">
          <div className="live-text-header">
            <span className="live-text-label">{liveLabel}</span>
            {alwaysOpen && <span className="live-text-cursor" />}
          </div>
          <pre className="live-text-pre" ref={liveRef}>
            {liveText}
          </pre>
        </div>
      )}
    </div>
  )
}

// ── Per-node output summaries ─────────────────────────────────────────────────

function StepOutput({ stepId, output }) {
  if (stepId === "medical_agent") return <MedicalOutput o={output} />
  if (stepId === "icd_agent")     return <IcdOutput o={output} />
  if (stepId === "damages_agent") return <DamagesOutput o={output} />
  if (stepId === "legal_agent")   return <LegalOutput o={output} />
  return null
}

function MedicalOutput({ o }) {
  const { injuries_count = 0, total_billed = 0, parsed_lost_wages = 0, parsed_future_care = 0, sample_injuries = [] } = o
  return (
    <div className="step-output">
      <div className="step-chips">
        <Chip label="Events" value={injuries_count} />
        {total_billed > 0 && <Chip label="Billed" value={`$${total_billed.toLocaleString()}`} accent />}
        {parsed_lost_wages > 0 && <Chip label="Lost wages" value={`$${parsed_lost_wages.toLocaleString()}`} green />}
        {parsed_future_care > 0 && <Chip label="Future care" value={`$${parsed_future_care.toLocaleString()}`} green />}
      </div>
      {sample_injuries.length > 0 && (
        <div className="step-tags">
          {sample_injuries.map((inj, i) => (
            <span key={i} className={`step-tag step-tag--${inj.severity_indicator || "moderate"}`}>
              {inj.description}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function IcdOutput({ o }) {
  const { diagnoses = [], total_events = 0 } = o
  return (
    <div className="step-output">
      <div className="step-chips">
        <Chip label="Total events" value={total_events} />
        <Chip label="Coded" value={diagnoses.length} accent />
      </div>
      {diagnoses.length > 0 && (
        <div className="icd-list">
          {diagnoses.map((d, i) => (
            <div key={i} className="icd-row">
              <span className="icd-code">{d.icd_code || "—"}</span>
              <span className="icd-desc">{d.description}</span>
              {d.ais_score != null && (
                <span className={`ais-badge ais-badge--${d.ais_score}`}>
                  AIS {d.ais_score} · {d.ais_label}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function DamagesOutput({ o }) {
  const { conservative = 0, mid_range = 0, high_end = 0, multiplier = 0, medical_specials = 0, case_opinions_count = 0 } = o
  return (
    <div className="step-output">
      <div className="damages-range">
        <RangeBox label="Conservative" value={conservative} tier="low" />
        <RangeBox label="Mid Range"    value={mid_range}    tier="mid" />
        <RangeBox label="High End"     value={high_end}     tier="high" />
      </div>
      <div className="step-chips" style={{ marginTop: 8 }}>
        {medical_specials > 0 && <Chip label="Specials" value={`$${medical_specials.toLocaleString()}`} />}
        {multiplier > 0 && <Chip label="Multiplier" value={`${multiplier}×`} accent />}
        {case_opinions_count > 0 && <Chip label="Case opinions" value={case_opinions_count} green />}
      </div>
    </div>
  )
}

function LegalOutput({ o }) {
  const { letter_preview = "", letter_length = 0 } = o
  return (
    <div className="step-output">
      <div className="step-chips">
        <Chip label="Letter" value={`${letter_length.toLocaleString()} chars`} accent />
      </div>
      {letter_preview && (
        <p className="letter-preview">"{letter_preview.trim()}…"</p>
      )}
    </div>
  )
}

// ── Micro-components ──────────────────────────────────────────────────────────

function Chip({ label, value, accent, green }) {
  return (
    <span className={`output-chip${accent ? " output-chip--accent" : ""}${green ? " output-chip--green" : ""}`}>
      <span className="chip-label">{label}</span>
      <strong>{value}</strong>
    </span>
  )
}

function RangeBox({ label, value, tier }) {
  return (
    <div className={`range-box range-box--${tier}`}>
      <span className="range-label">{label}</span>
      <span className="range-value">${(value || 0).toLocaleString()}</span>
    </div>
  )
}
