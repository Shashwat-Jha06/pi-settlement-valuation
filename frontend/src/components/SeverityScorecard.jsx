const AIS_TIER_COLORS = {
  1: { bg: "#dcfce7", border: "#86efac", text: "#16a34a", badge: "#22c55e" },
  2: { bg: "#dcfce7", border: "#86efac", text: "#16a34a", badge: "#22c55e" },
  3: { bg: "#fef9c3", border: "#fde047", text: "#ca8a04", badge: "#eab308" },
  4: { bg: "#fee2e2", border: "#fca5a5", text: "#dc2626", badge: "#ef4444" },
  5: { bg: "#fee2e2", border: "#fca5a5", text: "#dc2626", badge: "#ef4444" },
  6: { bg: "#fee2e2", border: "#fca5a5", text: "#dc2626", badge: "#ef4444" },
}

const CASE_TIER_LABELS = {
  1: "MINOR",
  2: "MODERATE",
  3: "SERIOUS",
  4: "SEVERE",
  5: "CRITICAL",
  6: "UNSURVIVABLE",
}

export default function SeverityScorecard({ injuries }) {
  const diagnoses = injuries.filter((i) => i.event_type === "diagnosis")
  const maxAis = diagnoses.length
    ? Math.max(...diagnoses.map((d) => d.ais_score || 1))
    : 1
  const colors = AIS_TIER_COLORS[maxAis] || AIS_TIER_COLORS[1]

  return (
    <div className="card">
      <h2 className="card-title">Severity Scorecard</h2>

      <div
        className="case-tier-banner"
        style={{ background: colors.bg, borderColor: colors.border, color: colors.text }}
      >
        <span className="tier-label">Overall Case Tier:</span>
        <span className="tier-value" style={{ color: colors.text }}>
          {CASE_TIER_LABELS[maxAis] || "UNKNOWN"}
        </span>
        <span className="tier-ais" style={{ background: colors.badge }}>
          AIS {maxAis}
        </span>
      </div>

      <div className="scorecard-grid">
        {diagnoses.map((injury, i) => {
          const c = AIS_TIER_COLORS[injury.ais_score] || AIS_TIER_COLORS[1]
          return (
            <div
              key={i}
              className="scorecard-card"
              style={{ borderColor: c.border, background: c.bg + "88" }}
            >
              <div className="scorecard-header">
                <span
                  className="ais-badge"
                  style={{ background: c.badge, color: "#fff" }}
                >
                  AIS {injury.ais_score}
                </span>
                <span className="ais-label-text" style={{ color: c.text }}>
                  {injury.ais_label}
                </span>
              </div>
              <p className="scorecard-description">{injury.description}</p>
              <div className="scorecard-meta">
                {injury.body_part && <span className="meta-chip">📍 {injury.body_part}</span>}
                {injury.icd_code && <span className="meta-chip icd">{injury.icd_code}</span>}
                {injury.permanent && <span className="meta-chip permanent">PERMANENT</span>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
