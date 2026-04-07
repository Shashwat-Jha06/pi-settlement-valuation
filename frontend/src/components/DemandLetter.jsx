import { useState } from "react"
import { Copy, Check, FileText, FileDown } from "lucide-react"

// ── PDF generator (jsPDF — pure client-side) ──────────────────────────────────
async function downloadPDF(letter) {
  const { jsPDF } = await import("jspdf")

  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "letter" })

  const marginLeft   = 25.4   // 1 inch
  const marginRight  = 25.4
  const marginTop    = 25.4
  const marginBottom = 25.4
  const pageW = doc.internal.pageSize.getWidth()
  const pageH = doc.internal.pageSize.getHeight()
  const textW = pageW - marginLeft - marginRight
  const lineH = 6.5           // ~11pt with 1.3 line spacing

  doc.setFont("times", "normal")
  doc.setFontSize(11)

  let y = marginTop

  const rawLines = letter.split("\n")

  for (const raw of rawLines) {
    // Blank line → paragraph gap
    if (!raw.trim()) {
      y += lineH * 0.6
      continue
    }

    // Detect section headings (ALL-CAPS short lines) → bold
    const isHeading = raw === raw.toUpperCase() && raw.trim().length > 2 && raw.trim().length < 80
    doc.setFont("times", isHeading ? "bold" : "normal")

    const wrapped = doc.splitTextToSize(raw, textW)

    for (const segment of wrapped) {
      if (y + lineH > pageH - marginBottom) {
        doc.addPage()
        y = marginTop
      }
      doc.text(segment, marginLeft, y)
      y += lineH
    }
  }

  // Page numbers in footer
  const totalPages = doc.internal.getNumberOfPages()
  for (let p = 1; p <= totalPages; p++) {
    doc.setPage(p)
    doc.setFont("times", "normal")
    doc.setFontSize(9)
    doc.setTextColor(120)
    doc.text(`Page ${p} of ${totalPages}`, pageW / 2, pageH - 10, { align: "center" })
    doc.setTextColor(0)
  }

  doc.save("demand_letter.pdf")
}

// ── Word (.docx) generator (docx — pure client-side) ─────────────────────────
async function downloadWord(letter) {
  const { Document, Paragraph, TextRun, Packer } = await import("docx")

  const TWIP = (inches) => Math.round(inches * 1440)

  const paragraphs = []

  for (const raw of letter.split("\n")) {
    const trimmed = raw.trim()

    // Empty line → blank paragraph spacer
    if (!trimmed) {
      paragraphs.push(new Paragraph({ spacing: { after: 80 } }))
      continue
    }

    // ALL-CAPS lines are section headings
    const isHeading =
      trimmed === trimmed.toUpperCase() && trimmed.length > 2 && trimmed.length < 80

    // "Re:" subject line
    const isSubject = /^re:/i.test(trimmed)

    // Damages table rows (lines with $)
    const isDollarLine = /\$[\d,]+/.test(trimmed) && trimmed.startsWith("-")

    paragraphs.push(
      new Paragraph({
        spacing: { after: isHeading ? 160 : 100, line: 276 },
        alignment: "left",
        children: [
          new TextRun({
            text: raw,
            font: "Times New Roman",
            size: isHeading ? 24 : 22,        // 12pt heading / 11pt body (half-points)
            bold: isHeading || isSubject || isDollarLine,
            italics: isSubject,
          }),
        ],
      })
    )
  }

  const doc = new Document({
    styles: {
      default: {
        document: {
          run: { font: "Times New Roman", size: 22 },
        },
      },
    },
    sections: [
      {
        properties: {
          page: {
            margin: {
              top:    TWIP(1),
              bottom: TWIP(1),
              left:   TWIP(1.25),
              right:  TWIP(1.25),
            },
          },
        },
        children: paragraphs,
      },
    ],
  })

  const blob = await Packer.toBlob(doc)
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement("a")
  a.href     = url
  a.download = "demand_letter.docx"
  a.click()
  URL.revokeObjectURL(url)
}

// ── Plain-text download (original) ───────────────────────────────────────────
function downloadTxt(letter) {
  const blob = new Blob([letter], { type: "text/plain" })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement("a")
  a.href     = url
  a.download = "demand_letter.txt"
  a.click()
  URL.revokeObjectURL(url)
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function DemandLetter({ letter }) {
  const [copied,    setCopied]    = useState(false)
  const [pdfBusy,   setPdfBusy]   = useState(false)
  const [wordBusy,  setWordBusy]  = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(letter)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handlePDF = async () => {
    setPdfBusy(true)
    try { await downloadPDF(letter) } finally { setPdfBusy(false) }
  }

  const handleWord = async () => {
    setWordBusy(true)
    try { await downloadWord(letter) } finally { setWordBusy(false) }
  }

  return (
    <div className="card demand-card">
      <div className="demand-header">
        <div>
          <h2 className="card-title">Demand Letter</h2>
          <p className="demand-subtitle">
            {letter.length.toLocaleString()} characters · download as PDF, Word, or plain text
          </p>
        </div>

        <div className="demand-actions">
          {/* Copy */}
          <button className="action-btn" onClick={handleCopy} title="Copy to clipboard">
            {copied ? <Check size={15} /> : <Copy size={15} />}
            {copied ? "Copied!" : "Copy"}
          </button>

          {/* PDF */}
          <button
            className="action-btn action-btn--pdf"
            onClick={handlePDF}
            disabled={pdfBusy}
            title="Download as PDF"
          >
            {pdfBusy
              ? <span className="spinner tiny" />
              : <FileDown size={15} />}
            {pdfBusy ? "Generating…" : "PDF"}
          </button>

          {/* Word */}
          <button
            className="action-btn action-btn--word"
            onClick={handleWord}
            disabled={wordBusy}
            title="Download as Word (.docx)"
          >
            {wordBusy
              ? <span className="spinner tiny" />
              : <FileText size={15} />}
            {wordBusy ? "Generating…" : "Word"}
          </button>

          {/* Plain text */}
          <button
            className="action-btn action-btn--txt"
            onClick={() => downloadTxt(letter)}
            title="Download as plain text"
          >
            .txt
          </button>
        </div>
      </div>

      {/* Letter viewer */}
      <div className="demand-viewer">
        <div className="demand-paper">
          <pre className="demand-text">{letter}</pre>
        </div>
      </div>
    </div>
  )
}
