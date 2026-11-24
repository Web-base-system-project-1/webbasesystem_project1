import { useState } from 'react'
import useApi from '../hooks/useApi'
const names = {
  original: '원본',
  step_x2: '2배 증가',
  step_x3: '3배 증가',
  step_x5: '5배 증가',
  gradual_x3: '점진 증가',
  spike_x5: '한 해 급증',
  decoy_x3: '미끼',
}
export default function CorrectionView({ selection, version, onSelect }) {
  const [scenario, setScenario] = useState('step_x3')
  const [detector, setDetector] = useState('growth')
  const [threshold, setThreshold] = useState('1')
  const correction =
    detector === 'growth'
      ? 'require_share_increase'
      : 'min_international_total_3'
  const runs = useApi('/api/experiments', version)
  const scenarios = [
    ...new Set(
      runs.data?.items
        .filter((r) => r.correction_id === correction)
        .map((r) => r.scenario_id) || [],
    ),
  ]
  const ready =
    Object.values(selection).every(Boolean) && scenarios.includes(scenario)
  const query = new URLSearchParams({
    ...selection,
    scenario_id: scenario,
    detector,
    threshold,
    correction_id: correction,
  })
  const { data, error, reload } = useApi(
    ready ? `/api/experiment-timeline?${query}` : null,
    version,
  )
  const before = data?.before_metrics,
    after = data?.metrics
  const removed =
    data?.before_detections.filter(
      (d) => !data.detections.some((a) => a.year === d.year),
    ) || []
  const added =
    data?.detections.filter(
      (d) => !data.before_detections.some((a) => a.year === d.year),
    ) || []
  const show = (k, v) =>
    v == null
      ? '—'
      : ['precision', 'recall', 'recall_effective'].includes(k)
        ? `${(v * 100).toFixed(1)}%`
        : ['f1', 'delay_mean'].includes(k)
          ? Number(v).toFixed(3)
          : v
  return (
    <section aria-label="보정 전후 비교">
      <h2>보정 전후 비교</h2>
      <p className="view-note">
        같은 데이터·시나리오·시드·임계값의 저장 결과를 비교합니다.{' '}
        {detector === 'growth'
          ? '증가율 탐지 중 협력 비중도 전년보다 증가한 경우만 유지합니다.'
          : '해당 연도 국내 기관 국제 공동논문이 3편 이상인 탐지만 유지합니다.'}
      </p>
      <div className="detection-filters">
        <label>
          보정 시나리오
          <select
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
          >
            {scenarios.map((s) => (
              <option key={s} value={s}>
                {names[s] || s}
              </option>
            ))}
          </select>
        </label>
        <label>
          보정 탐지기
          <select
            value={detector}
            onChange={(e) => {
              setDetector(e.target.value)
              setThreshold(e.target.value === 'growth' ? '1' : '2.5')
            }}
          >
            <option value="growth">증가율 · 비중 동반 증가</option>
            <option value="zscore">Z-score · 최소 분모 3편</option>
          </select>
        </label>
        <label>
          보정 임계값
          <select
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
          >
            {(detector === 'growth'
              ? ['0.5', '1', '2']
              : ['2', '2.5', '3']
            ).map((t) => (
              <option key={t} value={t}>
                {detector === 'growth' ? `${Number(t) * 100}%` : t}
              </option>
            ))}
          </select>
        </label>
      </div>
      {runs.error ? (
        <p role="alert">
          {runs.error} <button onClick={runs.reload}>다시 불러오기</button>
        </p>
      ) : !runs.data ? (
        <p role="status">보정 목록을 불러오는 중입니다.</p>
      ) : !scenarios.length ? (
        <p role="status">이 데이터에는 보정 후 저장 결과가 없습니다.</p>
      ) : !ready ? (
        <p role="status">위에서 비교할 기관 쌍을 선택해 주세요.</p>
      ) : error ? (
        <p role="alert">
          {error} <button onClick={reload}>다시 불러오기</button>
        </p>
      ) : !data ? (
        <p role="status">보정 결과를 불러오는 중입니다.</p>
      ) : (
        <>
          <h3>전체 실험 지표</h3>
          <p className="view-note">
            선택한 기관이 아닌 전체 실험의 평가입니다. FP는 주입 정답에 없는
            탐지로, 실제 연구의 이상 여부와 다릅니다. TP 감소·FN 증가도 함께
            확인하세요.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>지표</th>
                  <th>보정 전</th>
                  <th>보정 후</th>
                  <th>변화</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['tp', '정탐 TP'],
                  ['fp', '실험상 오탐 FP'],
                  ['fn', '미탐 FN'],
                  ['precision', 'Precision'],
                  ['recall', 'Recall'],
                  ['f1', 'F1'],
                  ['delay_mean', '평균 탐지 지연(년)'],
                  ['decoy_fp', '미끼 탐지'],
                ].map(([k, label]) => (
                  <tr key={k}>
                    <th>{label}</th>
                    <td>{show(k, before?.[k])}</td>
                    <td>{show(k, after?.[k])}</td>
                    <td>
                      {before?.[k] == null || after?.[k] == null
                        ? '—'
                        : show(k, after[k] - before[k])}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3>선택한 기관 쌍의 판정 변화</h3>
          <p>
            탐지 해제 {removed.length}건 · 새 탐지 {added.length}건
          </p>
          {!removed.length && !added.length ? (
            <p role="status">이 기관 쌍에서는 판정 변화가 없습니다.</p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>연도</th>
                    <th>변화</th>
                    <th>기존 점수</th>
                    <th>주입 정답 기준 판정</th>
                    <th>근거</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ...removed.map((d) => ({ ...d, change: '탐지 해제' })),
                    ...added.map((d) => ({ ...d, change: '새 탐지' })),
                  ].map((d) => (
                    <tr key={`${d.year}:${d.change}`}>
                      <th>
                        <button
                          className="pair-link"
                          onClick={() =>
                            onSelect({ ...selection, year: d.year })
                          }
                        >
                          {d.year}
                        </button>
                      </th>
                      <td>{d.change}</td>
                      <td>{show('f1', d.score)}</td>
                      <td>
                        {data.injections.some((i) => i.year === d.year)
                          ? d.change === '탐지 해제'
                            ? '정탐 해제 → 새 미탐'
                            : '미탐 해소 → 정탐'
                          : d.change === '탐지 해제'
                            ? '실험상 오탐 해소'
                            : '새 실험상 오탐'}
                      </td>
                      <td>
                        {detector === 'growth'
                          ? '협력 비중 동반 증가 조건'
                          : '국내 기관 국제 공동논문 3편 조건'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {data.target && (
            <button
              className="pair-link"
              onClick={() => onSelect({ ...data.target, year: 2021 })}
            >
              대표 주입 대상 선택
            </button>
          )}
        </>
      )}
    </section>
  )
}
