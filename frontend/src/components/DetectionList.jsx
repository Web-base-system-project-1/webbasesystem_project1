import { useState } from 'react'

const labels = { zscore: 'Z-score', growth: '증가율' }
const format = (value, detector) =>
  value == null
    ? '—'
    : detector === 'growth'
      ? `${(value * 100).toFixed(1)}%`
      : value.toFixed(2)

export default function DetectionList({ detections, onSelect }) {
  const [detector, setDetector] = useState('all')
  const [order, setOrder] = useState('year')
  const rows = detections
    .filter((row) => detector === 'all' || row.detector === detector)
    .toSorted((a, b) =>
      order === 'score'
        ? a.detector.localeCompare(b.detector) ||
          b.score - a.score ||
          b.year - a.year
        : b.year - a.year ||
          a.detector.localeCompare(b.detector) ||
          a.threshold - b.threshold,
    )

  return (
    <section className="detections" aria-label="탐지 결과">
      <div className="chart-heading">
        <div>
          <h2>
            탐지 결과 <span className="unit">{rows.length}건</span>
          </h2>
          <p>기관 쌍을 선택하면 해당 타임라인과 탐지 연도로 이동합니다.</p>
        </div>
      </div>
      <div className="detection-filters">
        <label>
          탐지 방법
          <select
            value={detector}
            onChange={(event) => setDetector(event.target.value)}
          >
            <option value="all">전체</option>
            <option value="zscore">Z-score</option>
            <option value="growth">증가율</option>
          </select>
        </label>
        <label>
          정렬
          <select
            value={order}
            onChange={(event) => setOrder(event.target.value)}
          >
            <option value="year">최근 연도순</option>
            <option value="score">방법별 점수 높은 순</option>
          </select>
        </label>
      </div>
      <p className="detection-note">
        같은 연도라도 탐지 방법·임계값이 다르면 별도 결과입니다. 점수는 탐지
        방법별로 비교합니다.
      </p>
      {rows.length === 0 ? (
        <p role="status" className="detection-note">
          선택한 조건의 탐지 결과가 없습니다.
        </p>
      ) : (
        <div className="table-scroll">
          <table>
            <caption className="sr-only">
              선택한 기관 쌍의 저장된 탐지 결과
            </caption>
            <thead>
              <tr>
                <th scope="col">연도</th><th scope="col">기관 쌍 · 분야</th>
                <th scope="col">탐지 방법</th>
                <th scope="col">점수</th>
                <th scope="col">임계값</th>
                <th scope="col">공동논문 수</th>
                <th scope="col">시나리오</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr
                  key={`${row.run_id}-${row.scenario_id}-${row.year}-${row.detector}-${row.threshold}-${row.correction_id}-${index}`}
                >
                  <th scope="row">{row.year}</th>
                  <td><button className="pair-link" onClick={() => onSelect(row)}>{row.domestic_name || row.domestic_id} / {row.foreign_name || row.foreign_id} · {row.field}</button></td>
                  <td>{labels[row.detector] || row.detector}</td>
                  <td>{format(row.score, row.detector)}</td>
                  <td>{format(row.threshold, row.detector)}</td>
                  <td>{row.collab_count ?? '—'}</td>
                  <td>{row.scenario_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
