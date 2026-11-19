const number = new Intl.NumberFormat('ko-KR')

export default function TimelineChart({
  points,
  selectedYear,
  comparisonPoints = [],
}) {
  const width = 960,
    height = 310
  const left = 48,
    right = 24,
    top = 24,
    bottom = 44
  const valid = points.filter((p) => Number.isFinite(p.collab_count))
  const maximum = Math.max(
    4,
    ...valid.map((p) => p.collab_count),
    ...comparisonPoints
      .filter((p) => Number.isFinite(p.collab_count))
      .map((p) => p.collab_count),
  )
  const step = Math.max(1, Math.ceil(maximum / 4))
  const ceiling = step * 4
  const x = (i) =>
    left + (i * (width - left - right)) / Math.max(1, points.length - 1)
  const y = (value) =>
    height - bottom - (value / ceiling) * (height - top - bottom)
  const path = points
    .map((p, i) =>
      Number.isFinite(p.collab_count)
        ? `${i === 0 || !Number.isFinite(points[i - 1].collab_count) ? 'M' : 'L'} ${x(i)} ${y(p.collab_count)}`
        : '',
    )
    .join(' ')
  return (
    <svg
      className="chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="연도별 공동논문 수 꺾은선 차트. 아래 연도별 수치에서 정확한 값을 확인할 수 있습니다."
    >
      {[0, 1, 2, 3, 4].map((i) => (
        <g key={i}>
          <line
            x1={left}
            x2={width - right}
            y1={y(i * step)}
            y2={y(i * step)}
            className="grid-line"
          />
          <text x={left - 14} y={y(i * step) + 4} textAnchor="end">
            {i * step}
          </text>
        </g>
      ))}
      {comparisonPoints.length > 0 && (
        <path
          d={comparisonPoints
            .map((p, i) =>
              Number.isFinite(p.collab_count)
                ? `${i === 0 || !Number.isFinite(comparisonPoints[i - 1].collab_count) ? 'M' : 'L'} ${x(i)} ${y(p.collab_count)}`
                : '',
            )
            .join(' ')}
          fill="none"
          stroke="#999d96"
          strokeWidth="2"
          strokeDasharray="6 5"
        />
      )}
      <path d={path} fill="none" className="series-line" />
      {points.map((p, i) => (
        <g key={p.year}>
          {(points.length <= 12 ||
            i % Math.ceil(points.length / 11) === 0 ||
            i === points.length - 1) && (
            <text x={x(i)} y={height - 12} textAnchor="middle">
              {p.year}
            </text>
          )}
          {Number.isFinite(p.collab_count) && (
            <circle
              cx={x(i)}
              cy={y(p.collab_count)}
              r={p.year === selectedYear ? 7 : 4}
              className={
                p.year === selectedYear
                  ? 'series-dot selected-dot'
                  : 'series-dot'
              }
            >
              <title>
                {p.year}년: {number.format(p.collab_count)}편
              </title>
            </circle>
          )}
        </g>
      ))}
    </svg>
  )
}
