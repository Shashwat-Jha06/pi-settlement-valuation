function fmt(n) {
  return "$" + Number(n).toLocaleString()
}

const JURISDICTION_NAMES = {
  CA: "California",
  NY: "New York",
  TX: "Texas",
  FL: "Florida",
  IL: "Illinois",
}

export default function ValuationReport({ valuation }) {
  const {
    medical_specials,
    lost_wages,
    future_care,
    economic_damages,
    multiplier,
    non_economic_damages,
    conservative,
    mid_range,
    high_end,
    max_ais,
    jurisdiction,
    jurisdiction_factor,
    has_permanent,
  } = valuation

  const adjustmentPct = ((jurisdiction_factor - 1) * 100).toFixed(0)
  const adjustmentLabel =
    adjustmentPct >= 0
      ? `${JURISDICTION_NAMES[jurisdiction] || jurisdiction} (+${adjustmentPct}%)`
      : `${JURISDICTION_NAMES[jurisdiction] || jurisdiction} (${adjustmentPct}%)`

  return (
    <div className="card">
      <h2 className="card-title">Settlement Valuation Report</h2>

      <table className="valuation-table">
        <tbody>
          <tr>
            <td>Medical Specials (Billed)</td>
            <td className="amount">{fmt(medical_specials)}</td>
          </tr>
          <tr>
            <td>Lost Wages</td>
            <td className="amount">{fmt(lost_wages)}</td>
          </tr>
          <tr>
            <td>Future Medical Care</td>
            <td className="amount">{fmt(future_care)}</td>
          </tr>
          <tr className="subtotal-row">
            <td>Economic Damages (Total)</td>
            <td className="amount">{fmt(economic_damages)}</td>
          </tr>
          <tr>
            <td>
              Pain &amp; Suffering
              <span className="multiplier-badge">×{multiplier}</span>
              {has_permanent && <span className="perm-note"> (permanent)</span>}
            </td>
            <td className="amount">{fmt(non_economic_damages)}</td>
          </tr>
        </tbody>
      </table>

      <div className="settlement-boxes">
        <div className="settlement-box conservative">
          <span className="box-label">Conservative</span>
          <span className="box-amount">{fmt(conservative)}</span>
        </div>
        <div className="settlement-box mid">
          <span className="box-label">Mid-Range</span>
          <span className="box-amount">{fmt(mid_range)}</span>
        </div>
        <div className="settlement-box high">
          <span className="box-label">High-End</span>
          <span className="box-amount">{fmt(high_end)}</span>
        </div>
      </div>

      <p className="jurisdiction-note">
        Jurisdiction adjustment applied: {adjustmentLabel} · Max AIS: {max_ais}
      </p>
    </div>
  )
}
