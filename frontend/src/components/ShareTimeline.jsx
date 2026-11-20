export default function ShareTimeline({
  points,
  baseline,
  detections,
  injections,
  selectedYear,
}) {
  const w = 960,
    h = 280,
    l = 48,
    r = 20,
    t = 18,
    b = 42
  const x = (i) => l + (i * (w - l - r)) / Math.max(1, points.length - 1)
  const y = (v) => h - b - v * (h - t - b)
  const lookup = new Map(baseline.map((p) => [p.year, p]))
  const path = (key) =>
    points
      .map((p, i) => {
        const value = key === 'share' ? p.share : lookup.get(p.year)?.[key]
        const prev = i
          ? key === 'share'
            ? points[i - 1].share
            : lookup.get(points[i - 1].year)?.[key]
          : null
        return Number.isFinite(value)
          ? `${i === 0 || !Number.isFinite(prev) ? 'M' : 'L'} ${x(i)} ${y(value)}`
          : ''
      })
      .join(' ')
  return (
    <section className="share-timeline">
      <h3>협력 비중과 과거 기준선</h3>
      <p className="view-note">
        초록: 협력 비중 · 회색 점선: 직전 3년 평균 · 회색 띠: 평균 ±
        표준편차(0~100%로 표시 범위 제한) · 주황 점: 탐지 · 주입 연도는 표에서
        확인할 수 있습니다.
      </p>
      <div className="chart-scroll">
        <svg
          className="chart"
          viewBox={`0 0 ${w} ${h}`}
          role="img"
          aria-label="연도별 협력 비중과 직전 3년 기준선 및 탐지 시점"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((v) => (
            <g key={v}>
              <line
                x1={l}
                x2={w - r}
                y1={y(v)}
                y2={y(v)}
                className="grid-line"
              />
              <text x={l - 8} y={y(v) + 4} textAnchor="end">
                {v * 100}%
              </text>
            </g>
          ))}
          {points.map((p, i) => {
            const base = lookup.get(p.year),
              next = points[i + 1] && lookup.get(points[i + 1].year)
            if (
              !base ||
              !next ||
              ![
                base.baseline_value,
                base.baseline_std,
                next.baseline_value,
                next.baseline_std,
              ].every(Number.isFinite)
            )
              return null
            const upper = (o) => Math.min(1, o.baseline_value + o.baseline_std),
              lower = (o) => Math.max(0, o.baseline_value - o.baseline_std)
            return (
              <polygon
                key={p.year}
                fill="#e0e4df"
                points={`${x(i)},${y(upper(base))} ${x(i + 1)},${y(upper(next))} ${x(i + 1)},${y(lower(next))} ${x(i)},${y(lower(base))}`}
              />
            )
          })}
          <path
            d={path('baseline_value')}
            fill="none"
            stroke="#858d83"
            strokeDasharray="5 4"
          />
          <path d={path('share')} fill="none" className="series-line" />
          {points.map((p, i) => (
            <g key={p.year}>
              <text x={x(i)} y={h - 12} textAnchor="middle">
                {p.year}
              </text>
              {Number.isFinite(p.share) && (
                <circle
                  cx={x(i)}
                  cy={y(p.share)}
                  r={p.year === selectedYear ? 6 : 3.5}
                  fill={
                    detections.some((d) => d.year === p.year)
                      ? '#b36b34'
                      : '#3e644e'
                  }
                >
                  <title>
                    {p.year}년 · {(p.share * 100).toFixed(1)}%
                  </title>
                </circle>
              )}
            </g>
          ))}
        </svg>
      </div>
      <details>
        <summary>기준선·탐지·주입 근거</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>연도</th>
                <th>비중</th>
                <th>과거 평균</th>
                <th>표준편차</th>
                <th>탐지</th>
                <th>주입</th>
                <th>계산 상태</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => {
                const base = lookup.get(p.year)
                const pct = (v) =>
                  Number.isFinite(v) ? `${(v * 100).toFixed(1)}%` : '—'
                return (
                  <tr key={p.year}>
                    <th>{p.year}</th>
                    <td>{pct(p.share)}</td>
                    <td>{pct(base?.baseline_value)}</td>
                    <td>{pct(base?.baseline_std)}</td>
                    <td>
                      {detections
                        .filter((d) => d.year === p.year)
                        .map((d) =>
                          d.detector === 'growth' ? '증가율' : 'Z-score',
                        )
                        .join(', ') || '—'}
                    </td>
                    <td>
                      {injections.some((d) => d.year === p.year) ? '있음' : '—'}
                    </td>
                    <td>
                      {{
                        insufficient_history: '과거 자료 부족',
                        zero_std: '표준편차 0',
                        missing_share: '비중 결측',
                      }[base?.skip_reason] ||
                        base?.skip_reason ||
                        '계산 가능'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  )
}
