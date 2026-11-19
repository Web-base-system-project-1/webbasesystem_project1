import { useEffect, useState } from 'react'
import { getData } from '../api/client'
import TimelineChart from './TimelineChart'

const names = {
  original: '원본',
  step_x2: '2배 지속 증가',
  step_x3: '3배 지속 증가',
  step_x5: '5배 지속 증가',
  gradual_x3: '점진 증가',
  spike_x5: '한 해 급증',
  decoy_x3: '미끼 · 전체 협력 동반 증가',
}
const percent = (value) =>
  value == null ? '—' : `${(value * 100).toFixed(1)}%`
const decimal = (value) => (value == null ? '—' : Number(value).toFixed(2))

export default function ExperimentView({ selection, version, onSelect }) {
  const [runsResult, setRunsResult] = useState(null)
  const [scenario, setScenario] = useState('step_x2')
  const [detector, setDetector] = useState('zscore')
  const [threshold, setThreshold] = useState('2.5')
  const [result, setResult] = useState(null)
  const [retry, setRetry] = useState(0)
  const runsKey = `${version}:${retry}`
  const query = new URLSearchParams({
    ...selection,
    scenario_id: scenario,
    detector,
    threshold,
  })
  const key = `${runsKey}:${query}`
  const current = result?.key === key ? result : null
  const runs = runsResult?.key === runsKey ? runsResult : null
  const ready = Object.values(selection).every(Boolean)
  useEffect(() => {
    const controller = new AbortController()
    getData('/api/experiments', controller.signal)
      .then((data) => {
        if (data.data_version !== version)
          throw new Error('데이터가 바뀌었습니다. 새로고침해 주세요.')
        if (!controller.signal.aborted) setRunsResult({ key: runsKey, data })
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setRunsResult({
            key: runsKey,
            error:
              error.status === 409
                ? '현재 데이터에는 저장된 실험 결과가 없습니다.'
                : error.message,
          })
      })
    return () => controller.abort()
  }, [version, runsKey])
  const queryString = query.toString()
  useEffect(() => {
    if (!ready || !runs?.data) return
    const controller = new AbortController()
    getData(`/api/experiment-timeline?${queryString}`, controller.signal)
      .then((data) => {
        if (data.data_version !== version)
          throw new Error('데이터가 바뀌었습니다. 새로고침해 주세요.')
        if (!controller.signal.aborted) setResult({ key, data })
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setResult({
            key,
            error:
              error.status === 404
                ? '이 기관 쌍 또는 설정의 실험 자료가 없습니다.'
                : error.message,
          })
      })
    return () => controller.abort()
  }, [ready, runs, key, queryString, version])
  if (runs?.error)
    return (
      <section className="experiment">
        <h2>주입 실험</h2>
        <p role="status">{runs.error}</p>
        <button onClick={() => setRetry((v) => v + 1)}>다시 불러오기</button>
      </section>
    )
  const data = current?.data
  const metric = data?.metrics
  return (
    <section className="experiment" aria-label="주입 실험 비교">
      <h2>원본과 주입 실험</h2>
      <p className="detection-note">
        위에서 선택한 기관 쌍을 같은 데이터 버전·시드의 실험과 비교합니다. 회색
        점선은 원본, 초록 실선은 선택한 시나리오입니다.
      </p>
      <div className="detection-filters">
        <label>
          시나리오
          <select
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
          >
            {[
              ...new Set(runs?.data?.items.map((r) => r.scenario_id) || []),
            ].map((id) => (
              <option key={id} value={id}>
                {names[id] || id}
              </option>
            ))}
          </select>
        </label>
        <label>
          실험 탐지 방법
          <select
            value={detector}
            onChange={(e) => {
              setDetector(e.target.value)
              setThreshold(e.target.value === 'zscore' ? '2.5' : '1')
            }}
          >
            <option value="zscore">Z-score</option>
            <option value="growth">증가율</option>
          </select>
        </label>
        <label>
          실험 임계값
          <select
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
          >
            {(detector === 'zscore'
              ? ['2', '2.5', '3']
              : ['0.5', '1', '2']
            ).map((v) => (
              <option key={v} value={v}>
                {detector === 'growth' ? percent(Number(v)) : v}
              </option>
            ))}
          </select>
        </label>
      </div>
      {!runs ? (
        <p role="status">실험 목록을 불러오는 중입니다.</p>
      ) : !ready ? (
        <p role="status">기관 쌍을 먼저 선택해 주세요.</p>
      ) : current?.error ? (
        <p role="alert">{current.error}</p>
      ) : !data ? (
        <p role="status">실험 결과를 불러오는 중입니다.</p>
      ) : (
        <>
          {data.target && (
            <button
              className="pair-link"
              onClick={() => onSelect({ ...data.target, year: 2021 })}
            >
              이 시나리오의 주입 대상 보기
            </button>
          )}
          <p className="detection-note">
            시드 {data.seed} · 보정 전 ·{' '}
            {data.injections.length
              ? `선택한 기관 쌍의 주입 정답 ${data.injections.length}행`
              : '선택한 기관 쌍에 직접 주입한 정답 행 없음'}
          </p>
          <div className="chart-scroll">
            <TimelineChart
              points={data.points}
              comparisonPoints={data.original}
            />
          </div>
          <details>
            <summary>원본·주입 수치와 탐지 근거</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>연도</th>
                    <th>원본 논문 수</th>
                    <th>시나리오 논문 수</th>
                    <th>원본 비중</th>
                    <th>시나리오 비중</th>
                    <th>주입 상태</th>
                    <th>탐지 점수 / 기준값</th>
                  </tr>
                </thead>
                <tbody>
                  {data.points.map((p) => {
                    const original = data.original.find(
                      (row) => row.year === p.year,
                    )
                    const truth = data.injections.find(
                      (row) => row.year === p.year,
                    )
                    const hit = data.detections.find(
                      (row) => row.year === p.year,
                    )
                    return (
                      <tr key={p.year}>
                        <th scope="row">{p.year}</th>
                        <td>{original?.collab_count ?? '—'}</td>
                        <td>{p.collab_count ?? '—'}</td>
                        <td>{percent(original?.share)}</td>
                        <td>{percent(p.share)}</td>
                        <td>
                          {truth
                            ? truth.effective
                              ? '실제 증가'
                              : '주입 예정 · 원본 0편'
                            : '—'}
                        </td>
                        <td>
                          {hit
                            ? `${detector === 'growth' ? percent(hit.score) : decimal(hit.score)} / ${detector === 'growth' ? hit.baseline_value : percent(hit.baseline_value)}`
                            : '선택 조건의 탐지 없음'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </details>
          <h3>전체 실험 평가</h3>
          <p className="detection-note">
            선택한 기관 쌍이 아닌 전체 실험의 지표입니다. 주입 정답에 없는
            탐지를 실험상 오탐으로 세며 실제 연구의 이상 여부 판정과 다릅니다.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>TP</th>
                  <th>FP</th>
                  <th>FN</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>F1</th>
                  <th>실제 증가 행 Recall</th>
                  <th>평균 지연</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{metric.tp}</td>
                  <td>{metric.fp}</td>
                  <td>{metric.fn}</td>
                  <td>{percent(metric.precision)}</td>
                  <td>{percent(metric.recall)}</td>
                  <td>{decimal(metric.f1)}</td>
                  <td>{percent(metric.recall_effective)}</td>
                  <td>
                    {metric.delay_mean == null
                      ? '—'
                      : `${decimal(metric.delay_mean)}년`}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
