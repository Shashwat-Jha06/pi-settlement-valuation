import { useState } from "react"
import UploadPanel from "./components/UploadPanel"
import InjuryTimeline from "./components/InjuryTimeline"
import SeverityScorecard from "./components/SeverityScorecard"
import ValuationReport from "./components/ValuationReport"
import DemandLetter from "./components/DemandLetter"
import CaseOpinions from "./components/CaseOpinions"
import PipelineProgress from "./components/PipelineProgress"
import { useCaseAnalysis } from "./hooks/useCaseAnalysis"
import "./App.css"

export default function App() {
  const { analyze, result, loading, error, steps } = useCaseAnalysis()
  const [showSample, setShowSample] = useState(false)

  const SAMPLE_TEXT = `Patient: [REDACTED] | Date of Injury: January 3, 2024

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

Lost work: 6 weeks @ $1,200/week = $7,200.`

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <div>
            <h1>PI Case Valuation Engine</h1>
            <p>Upload a medical record. Get a settlement estimate in seconds.</p>
          </div>
          <span className="powered-badge">Powered by Groq · Llama 3.3 70B</span>
        </div>
      </header>

      <main className="app-main">
        <UploadPanel onSubmit={analyze} loading={loading} />

        <div className="sample-row">
          <button
            className="sample-btn"
            type="button"
            onClick={() => setShowSample((v) => !v)}
          >
            {showSample ? "Hide" : "Show"} sample test input
          </button>
        </div>

        {showSample && (
          <pre className="sample-box">{SAMPLE_TEXT}</pre>
        )}

        {error && (
          <div className="error-box">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Pipeline progress — shown while loading and kept visible (collapsed) after done */}
        {(loading || result) && (
          <PipelineProgress steps={steps} />
        )}

        {result && (
          <>
            {(result.parsed_lost_wages > 0 || result.parsed_future_care > 0) && (
              <div className="autoparsed-banner">
                Auto-detected from record:
                {result.parsed_lost_wages > 0 && (
                  <span className="autoparsed-chip">
                    Lost wages: <strong>${result.parsed_lost_wages.toLocaleString()}</strong>
                  </span>
                )}
                {result.parsed_future_care > 0 && (
                  <span className="autoparsed-chip">
                    Future care: <strong>${result.parsed_future_care.toLocaleString()}</strong>
                  </span>
                )}
              </div>
            )}
            <div className="results-grid">
              <InjuryTimeline injuries={result.injuries} />
              <SeverityScorecard injuries={result.injuries} />
              <ValuationReport valuation={result.valuation} />
              {result.case_opinions?.length > 0 && (
                <CaseOpinions opinions={result.case_opinions} />
              )}
              <DemandLetter letter={result.demand_letter} />
            </div>
          </>
        )}
      </main>
    </div>
  )
}
