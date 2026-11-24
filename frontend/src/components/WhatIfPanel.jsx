import { useEffect, useRef, useState } from 'react'
import { getData } from '../api/client'
import {
  CORRECTION_RULES,
  DEFAULT_THRESHOLDS,
  defaultSettings,
  postWhatIf,
} from '../api/whatif'

const detectorLabels = { zscore: 'Z-score', growth: '증가율' }
const correctionLabels = {
  none: '보정 없음',
  min_international_total_3: '국제 공동논문 3편 이상만',
  require_share_increase: '협력 비중도 증가한 경우만',
}
const metricLabels = {
  tp: '정탐', fp: '오탐', fn: '미탐',
  precision: 'Precision', recall: 'Recall', f1: 'F1',
  delay_mean: '평균 탐지 지연', decoy_fp: '미끼 오탐',
}
const shown = ['tp', 'fp', 'fn', 'precision', 'recall', 'f1', 'decoy_fp']

const number = (value, digits = 3) =>
  value == null ? '—' : Number.isInteger(value) ? value : value.toFixed(digits)
const signed = (value, digits = 3) =>
  value == null || value === 0 ? '0' : `${value > 0 ? '+' : ''}${number(value, digits)}`

export default function WhatIfPanel() {
  const [settings, setSettings] = useState(defaultSettings())
  const [scenarios, setScenarios] = useState(['original'])
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const pending = useRef(null)

  useEffect(() => {
    const controller = new AbortController()
    getData('/api/scenarios', controller.signal)
      .then((body) => {
        const names = body.items.map((item) => item.scenario_id)
        setScenarios(names.length ? names : ['original'])
      })
      .catch(() => {
        // 시나리오 목록을 못 받아도 원본 재계산은 할 수 있다.
      })
    return () => controller.abort()
  }, [])

  useEffect(() => () => pending.current?.abort(), [])

  function change(event) {
    const { name, value } = event.target
    setSettings((previous) => {
      if (name === 'detector') {
        // 탐지기를 바꾸면 임계값과 보정은 그 탐지기의 기본값으로 되돌린다.
        return { ...previous, detector: value, threshold: DEFAULT_THRESHOLDS[value], correction_id: 'none' }
      }
      return {
        ...previous,
        [name]: name === 'threshold' || name === 'k' || name === 'min_count'
          ? Number(value)
          : value,
      }
    })
  }

  async function recompute(event) {
    event.preventDefault()
    pending.current?.abort()
    const controller = new AbortController()
    pending.current = controller
    setLoading(true)
    setError(null)
    try {
      setResult(await postWhatIf(settings, controller.signal))
    } catch (cause) {
      if (cause.name === 'AbortError') return
      setResult(null)
      setError(cause.message)
    } finally {
      if (pending.current === controller) setLoading(false)
    }
  }

  const corrections = ['none', CORRECTION_RULES[settings.detector]]
  const changed = result?.items ?? []

  return (
    <section className="whatif" aria-label="What-if 재계산">
      <div className="chart-heading">
        <div>
          <h2>What-if</h2>
          <p>
            설정을 바꿔 다시 계산합니다. 기준은 명세의 기본 설정
            (Z-score 2.5 · 증가율 1.0 · k 3 · 최소 건수 3 · 보정 없음) 입니다.
          </p>
        </div>
      </div>

      <form className="whatif-form" onSubmit={recompute}>
        <label>
          탐지 방법
          <select name="detector" value={settings.detector} onChange={change}>
            {Object.entries(detectorLabels).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label>
          임계값
          <input
            type="number" name="threshold" step="0.1"
            value={settings.threshold} onChange={change}
          />
        </label>
        <label>
          기준 기간 k
          <input
            type="number" name="k" min="2" max="10" step="1"
            value={settings.k} onChange={change}
          />
        </label>
        <label>
          최소 건수
          <input
            type="number" name="min_count" min="0" step="1"
            value={settings.min_count} onChange={change}
          />
        </label>
        <label>
          시나리오
          <select name="scenario_id" value={settings.scenario_id} onChange={change}>
            {scenarios.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </label>
        <label>
          보정
          <select name="correction_id" value={settings.correction_id} onChange={change}>
            {corrections.map((name) => (
              <option key={name} value={name}>{correctionLabels[name] ?? name}</option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={loading}>
          {loading ? '계산 중…' : '다시 계산'}
        </button>
      </form>

      {error && <p className="error" role="alert">{error}</p>}

      {result && !error && (
        <>
          <p className="whatif-summary">
            탐지 <strong>{result.counts.baseline}건</strong> →{' '}
            <strong>{result.counts.current}건</strong>
            {' · '}새로 생김 <strong>{result.counts.added}건</strong>
            {' · '}사라짐 <strong>{result.counts.removed}건</strong>
            {result.cached.current && <span className="unit"> (보관한 결과)</span>}
          </p>

          {result.metrics ? (
            <table className="whatif-metrics">
              <caption>
                기준 {detectorLabels[result.baseline.detector]} {result.baseline.threshold}
                {' → '}
                {detectorLabels[result.params.detector]} {result.params.threshold}
              </caption>
              <thead>
                <tr>
                  <th scope="col">지표</th>
                  <th scope="col">기준</th>
                  <th scope="col">바꾼 설정</th>
                  <th scope="col">차이</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((name) => (
                  <tr key={name}>
                    <th scope="row">{metricLabels[name] ?? name}</th>
                    <td>{number(result.baseline_metrics?.[name])}</td>
                    <td>{number(result.metrics[name])}</td>
                    <td>{signed(result.delta?.[name])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="detection-note">
              이 데이터에는 주입 정답이 없어 지표를 낼 수 없습니다. 탐지 증감만 보입니다.
            </p>
          )}

          <h3>
            바뀐 탐지 <span className="unit">{result.total}건</span>
          </h3>
          {changed.length === 0 ? (
            <p className="detection-note">설정을 바꿔도 탐지 결과가 같습니다.</p>
          ) : (
            <table className="whatif-changes">
              <thead>
                <tr>
                  <th scope="col">변화</th>
                  <th scope="col">국내 기관</th>
                  <th scope="col">해외 기관</th>
                  <th scope="col">분야</th>
                  <th scope="col">연도</th>
                  <th scope="col">점수</th>
                  <th scope="col">주입 정답</th>
                </tr>
              </thead>
              <tbody>
                {changed.map((row) => (
                  <tr key={`${row.change}|${row.domestic_id}|${row.foreign_id}|${row.field}|${row.year}`}>
                    <td className={row.change === 'added' ? 'change-added' : 'change-removed'}>
                      {row.change === 'added' ? '새로 생김' : '사라짐'}
                    </td>
                    <td>{row.domestic_name}</td>
                    <td>
                      {row.foreign_name}
                      {row.foreign_country && <span className="unit"> ({row.foreign_country})</span>}
                    </td>
                    <td>{row.field}</td>
                    <td>{row.year}</td>
                    <td>{number(row.score, 2)}</td>
                    <td>{row.was_injected ? '예' : '아니오'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {result.total > changed.length && (
            <p className="detection-note">
              {result.total}건 중 {changed.length}건만 표시했습니다.
            </p>
          )}
        </>
      )}
    </section>
  )
}
