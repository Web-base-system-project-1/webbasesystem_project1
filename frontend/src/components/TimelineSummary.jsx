const number = new Intl.NumberFormat('ko-KR')

export default function TimelineSummary({ points }) {
  const counts = points.filter((p) => Number.isFinite(p.collab_count))
  const total = counts.reduce((sum, p) => sum + p.collab_count, 0)
  const peak = counts.length
    ? Math.max(...counts.map((p) => p.collab_count))
    : null
  const peakYears = counts
    .filter((p) => p.collab_count === peak)
    .map((p) => p.year)
    .join(', ')

  return (
    <div className="summary">
      <p>
        기간 합계 <strong>{counts.length ? number.format(total) : '—'}</strong>
        <span>편{counts.length < points.length ? ' · 결측 제외' : ''}</span>
      </p>
      <p>
        연간 최다 <strong>{peak === null ? '—' : number.format(peak)}</strong>
        <span>편{peakYears ? ` · ${peakYears}년` : ''}</span>
      </p>
    </div>
  )
}
