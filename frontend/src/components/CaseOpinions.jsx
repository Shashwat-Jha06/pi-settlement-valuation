import { ExternalLink } from "lucide-react"

function formatDate(dateStr) {
  if (!dateStr) return ""
  try {
    return new Date(dateStr).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })
  } catch {
    return dateStr
  }
}

export default function CaseOpinions({ opinions }) {
  if (!opinions || opinions.length === 0) return null

  return (
    <div className="card">
      <div className="opinions-header">
        <h2 className="card-title">Relevant Case Law</h2>
        <span className="opinions-source">via CourtListener</span>
      </div>

      <div className="opinions-list">
        {opinions.map((op, i) => (
          <div key={i} className="opinion-row">
            <div className="opinion-top">
              <span className="opinion-name">{op.case_name || "Unnamed Case"}</span>
              <div className="opinion-meta">
                {op.court && <span className="meta-chip">{op.court}</span>}
                {op.date && <span className="meta-chip">{formatDate(op.date)}</span>}
              </div>
            </div>

            {op.snippet && (
              <p className="opinion-snippet">
                <span className="snippet-quote">"</span>
                {op.snippet.replace(/<[^>]+>/g, "").trim()}
                <span className="snippet-quote">"</span>
              </p>
            )}

            {op.url && (
              <a
                href={op.url}
                target="_blank"
                rel="noopener noreferrer"
                className="opinion-link"
              >
                View full opinion <ExternalLink size={12} />
              </a>
            )}
          </div>
        ))}
      </div>

      <p className="opinions-disclaimer">
        Case law retrieved for research context only. Not legal advice.
      </p>
    </div>
  )
}
