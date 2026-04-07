import { AlertTriangle } from "lucide-react"

const EVENT_COLORS = {
  diagnosis: "#6366f1",
  treatment: "#10b981",
  surgery: "#ef4444",
  imaging: "#f59e0b",
  therapy: "#3b82f6",
  follow_up: "#8b5cf6",
}

const EVENT_LABELS = {
  diagnosis: "Diagnosis",
  treatment: "Treatment",
  surgery: "Surgery",
  imaging: "Imaging",
  therapy: "Therapy",
  follow_up: "Follow-Up",
}

function formatDate(dateStr) {
  if (!dateStr) return "Date Unknown"
  try {
    return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric"
    })
  } catch {
    return dateStr
  }
}

export default function InjuryTimeline({ injuries }) {
  const sorted = [...injuries].sort((a, b) => {
    if (!a.date && !b.date) return 0
    if (!a.date) return 1
    if (!b.date) return -1
    return a.date.localeCompare(b.date)
  })

  return (
    <div className="card">
      <h2 className="card-title">Injury &amp; Treatment Timeline</h2>
      <div className="timeline">
        {sorted.map((item, i) => (
          <div key={i} className="timeline-row">
            <div className="timeline-line">
              <div
                className="timeline-dot"
                style={{ background: EVENT_COLORS[item.event_type] || "#94a3b8" }}
              />
              {i < sorted.length - 1 && <div className="timeline-connector" />}
            </div>

            <div className="timeline-content">
              <div className="timeline-header">
                <span className="date-chip">{formatDate(item.date)}</span>
                <span
                  className="event-badge"
                  style={{ background: EVENT_COLORS[item.event_type] + "22", color: EVENT_COLORS[item.event_type] }}
                >
                  {EVENT_LABELS[item.event_type] || item.event_type}
                </span>
                {item.permanent && (
                  <span className="permanent-tag">
                    <AlertTriangle size={12} /> PERMANENT
                  </span>
                )}
              </div>

              <p className="timeline-description">{item.description}</p>

              <div className="timeline-meta">
                {item.body_part && <span className="meta-chip">📍 {item.body_part}</span>}
                {item.icd_code && <span className="meta-chip icd">ICD: {item.icd_code}</span>}
                {item.medical_cost_billed > 0 && (
                  <span className="meta-chip cost">
                    ${item.medical_cost_billed.toLocaleString()}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
