import { useState, useCallback } from "react"
import { useDropzone } from "react-dropzone"
import { UploadCloud, FileText, X } from "lucide-react"

const JURISDICTIONS = ["CA", "NY", "TX", "FL", "IL", "OTHER"]

export default function UploadPanel({ onSubmit, loading }) {
  const [file, setFile] = useState(null)
  const [rawText, setRawText] = useState("")
  const [mode, setMode] = useState("file") // "file" | "text"
  const [jurisdiction, setJurisdiction] = useState("CA")
  const [lostWages, setLostWages] = useState("")
  const [futureCare, setFutureCare] = useState("")

  const onDrop = useCallback((accepted) => {
    if (accepted[0]) setFile(accepted[0])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
    disabled: loading,
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit({
      file: mode === "file" ? file : null,
      rawText: mode === "text" ? rawText : null,
      jurisdiction,
      lostWages: parseFloat(lostWages) || 0,
      futureCare: parseFloat(futureCare) || 0,
    })
  }

  const canSubmit = !loading && (mode === "file" ? !!file : rawText.trim().length > 20)

  return (
    <div className="upload-panel">
      <div className="mode-toggle">
        <button
          className={`toggle-btn ${mode === "file" ? "active" : ""}`}
          onClick={() => setMode("file")}
          type="button"
        >
          <UploadCloud size={16} /> Upload PDF
        </button>
        <button
          className={`toggle-btn ${mode === "text" ? "active" : ""}`}
          onClick={() => setMode("text")}
          type="button"
        >
          <FileText size={16} /> Paste Text
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        {mode === "file" ? (
          <div
            {...getRootProps()}
            className={`dropzone ${isDragActive ? "drag-over" : ""} ${file ? "has-file" : ""}`}
          >
            <input {...getInputProps()} />
            {file ? (
              <div className="file-preview">
                <FileText size={32} />
                <span className="file-name">{file.name}</span>
                <button
                  type="button"
                  className="remove-file"
                  onClick={(e) => { e.stopPropagation(); setFile(null) }}
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              <div className="drop-hint">
                <UploadCloud size={40} />
                <p>Drag &amp; drop a medical record PDF here</p>
                <span>or click to browse</span>
              </div>
            )}
          </div>
        ) : (
          <textarea
            className="text-input"
            placeholder="Paste clinical notes, ER reports, or medical records here..."
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            rows={10}
            disabled={loading}
          />
        )}

        <div className="form-row">
          <div className="form-group">
            <label>Jurisdiction</label>
            <select
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value)}
              disabled={loading}
            >
              {JURISDICTIONS.map((j) => (
                <option key={j} value={j}>{j}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Lost Wages ($)</label>
            <input
              type="number"
              min="0"
              placeholder="0"
              value={lostWages}
              onChange={(e) => setLostWages(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>Future Care Estimate ($)</label>
            <input
              type="number"
              min="0"
              placeholder="0"
              value={futureCare}
              onChange={(e) => setFutureCare(e.target.value)}
              disabled={loading}
            />
          </div>
        </div>

        <button type="submit" className="submit-btn" disabled={!canSubmit}>
          {loading ? (
            <span className="spinner-row"><span className="spinner" /> Analyzing with Groq…</span>
          ) : (
            "Analyze Case"
          )}
        </button>
      </form>
    </div>
  )
}
