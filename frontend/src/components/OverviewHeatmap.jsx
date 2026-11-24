import { useState } from 'react'
import useApi from '../hooks/useApi'

export default function OverviewHeatmap({ field, year, version, onCountry }) {
  const [measure, setMeasure] = useState('share')
  const query = new URLSearchParams({ field, limit: '1000', source: 'live' })
  if (year) query.set('year', year)
  const { data, error, reload } = useApi(`/api/overview?${query}`, version)
  if (error)
    return (
      <p role="alert">
        {error} <button onClick={reload}>다시 불러오기</button>
      </p>
    )
  if (!data) return <p role="status">국가별 집계를 불러오는 중입니다.</p>
  const countries = [...new Set(data.items.map((r) => r.country_code))].sort(
    (a, b) => String(a).localeCompare(String(b)),
  )
  const years = [...new Set(data.items.map((r) => r.year))].sort(
    (a, b) => a - b,
  )
  const cells = new Map(
    data.items.map((r) => [`${r.country_code}:${r.year}`, r]),
  )
  const unique = data.aggregation_basis === 'unique_country_papers'
  const colorValue = (r) =>
    measure === 'detections'
      ? Math.min(1, Math.log1p(r.detections) / Math.log(60))
      : unique
        ? r.share
        : r.composition
  return (
    <section aria-label="국가별 협력 히트맵">
      <div className="view-heading">
        <h2>국가별 협력</h2>
        <label>
          색상 기준
          <select value={measure} onChange={(e) => setMeasure(e.target.value)}>
            <option value="share">협력 비중</option>
            <option value="detections">탐지 건수</option>
          </select>
        </label>
      </div>
      <p className="view-note">
        전국 개요 · 분야·연도 조건 적용. 기관·유형 선택과는 별도입니다.{' '}
        {unique
          ? '같은 논문·국가의 중복을 제거한 비중입니다. 여러 나라가 참여하면 비중 합은 100%를 넘을 수 있습니다.'
          : '국가 고유 논문 표가 없어 기관 쌍 건수의 구성비로 색을 표시합니다.'}{' '}
        셀을 누르면 해당 국가의 기관 관계를 확인합니다.
      </p>
      {!data.items.length ? (
        <p role="status">해당 조건의 국가 집계가 없습니다.</p>
      ) : (
        <div className="heatmap-scroll">
          <table className="heatmap">
            <caption className="sr-only">
              국가와 연도별 협력 비중 및 탐지 건수
            </caption>
            <thead>
              <tr>
                <th scope="col">국가</th>
                {years.map((y) => (
                  <th key={y} scope="col">
                    {y}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {countries.map((country) => (
                <tr key={country || 'unknown'}>
                  <th scope="row">{country || '국가 불명'}</th>
                  {years.map((y) => {
                    const r = cells.get(`${country}:${y}`)
                    const proportion = unique ? r?.share : r?.composition
                    return (
                      <td key={y}>
                        {r ? (
                          <button
                            style={{
                              backgroundColor: `rgba(55, 105, 78, ${0.06 + 0.5 * (colorValue(r) || 0)})`,
                            }}
                            title={`${r.collab_count}편 · 비중 ${r.share == null ? '결측' : (r.share * 100).toFixed(1) + '%'} · 탐지 ${r.detections}건`}
                            onClick={() => onCountry(country, y)}
                          >
                            {measure === 'detections'
                              ? `${r.detections}건`
                              : Number.isFinite(proportion)
                                ? `${(proportion * 100).toFixed(1)}%`
                                : '—'}
                          </button>
                        ) : (
                          <span title="집계 행 없음">—</span>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data.count < data.total && (
        <p role="status">
          전체 {data.total}행 중 {data.count}행입니다. 연도로 범위를 좁혀
          주세요.
        </p>
      )}
    </section>
  )
}
