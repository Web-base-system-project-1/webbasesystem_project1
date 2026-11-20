import { useState } from 'react'
import useApi from '../hooks/useApi'
const initial = {
  scenario_id: 'step_x3',
  detector: 'zscore',
  threshold: 2.5,
  k: 3,
  min_count: 3,
  correction_id: 'none',
}
const scenarioNames = {
  original: '원본',
  step_x2: '2배 증가',
  step_x3: '3배 증가',
  step_x5: '5배 증가',
  gradual_x3: '점진 증가',
  spike_x5: '한 해 급증',
  decoy_x3: '미끼',
}
export default function WhatIfView({ version, onSelect }) {
  const [draft, setDraft] = useState(initial)
  const [applied, setApplied] = useState(null)
  const query = applied ? JSON.stringify(applied) : null
  const { data, error, reload } = useApi(
    applied ? '/api/whatif' : null,
    version,
    query,
  )
  const change = (e) => {
    const { name, value } = e.target
    setDraft((p) => ({
      ...p,
      [name]: ['k', 'min_count', 'threshold'].includes(name)
        ? Number(value)
        : value,
      ...(name === 'detector'
        ? { threshold: value === 'zscore' ? 2.5 : 1, correction_id: 'none' }
        : {}),
    }))
  }
  const correction =
    draft.detector === 'zscore'
      ? 'min_international_total_3'
      : 'require_share_increase'
  const display = (key, v) =>
    v == null
      ? '—'
      : ['precision', 'recall'].includes(key)
        ? `${(v * 100).toFixed(1)}%`
        : ['f1', 'delay_mean'].includes(key)
          ? Number(v).toFixed(3)
          : v
  return (
    <section aria-label="What-if 분석">
      <h2>설정 변경 실험</h2>
      <p className="view-note">
        같은 시나리오의 기본 설정(k=3, 최소 3편, Z-score 2.5 또는 증가율 100%,
        보정 없음)과 비교합니다. 재계산 결과는 전체 데이터 기준이며 위 기관·연도
        필터와 별도입니다.
      </p>
      <form
        className="whatif-form"
        onSubmit={(e) => {
          e.preventDefault()
          setApplied({ ...draft })
        }}
      >
        <label>
          What-if 시나리오
          <select
            name="scenario_id"
            value={draft.scenario_id}
            onChange={change}
          >
            {Object.entries(scenarioNames).map(([id, n]) => (
              <option key={id} value={id}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label>
          What-if 탐지기
          <select name="detector" value={draft.detector} onChange={change}>
            <option value="zscore">Z-score</option>
            <option value="growth">증가율</option>
          </select>
        </label>
        <label>
          임계값{draft.detector === 'growth' ? ' (1 = 100%)' : ''}
          <input
            name="threshold"
            type="number"
            min="0"
            max="1000"
            step="0.1"
            value={draft.threshold}
            onChange={change}
            required
          />
        </label>
        <label>
          과거 기준 연수 k
          <input
            name="k"
            type="number"
            min="2"
            max="10"
            step="1"
            disabled={draft.detector === 'growth'}
            value={draft.k}
            onChange={change}
            required
          />
        </label>
        <label>
          증가율 최소 논문 수
          <input
            name="min_count"
            type="number"
            min="0"
            max="100000"
            step="1"
            disabled={draft.detector === 'zscore'}
            value={draft.min_count}
            onChange={change}
            required
          />
        </label>
        <label>
          What-if 보정
          <select
            name="correction_id"
            value={draft.correction_id}
            onChange={change}
          >
            <option value="none">보정 없음</option>
            <option value={correction}>
              {draft.detector === 'zscore'
                ? '국내 총수 최소 3편'
                : '협력 비중 동반 증가'}
            </option>
          </select>
        </label>
        <button className="plain-button" type="submit">
          결과 재계산
        </button>
      </form>
      {!applied ? (
        <p role="status">설정을 입력하고 결과 재계산을 눌러 주세요.</p>
      ) : error ? (
        <p role="alert">
          {error} <button onClick={reload}>다시 계산</button>
        </p>
      ) : !data ? (
        <p role="status">탐지와 평가 지표를 계산하는 중입니다.</p>
      ) : (
        <>
          <p role="status">
            추가 탐지 {data.added_total}건 · 해제 탐지 {data.removed_total}건
          </p>
          <p className="view-note">
            적용한 설정: {data.params.detector} · 임계값 {data.params.threshold}{' '}
            · k {data.params.k} · 최소 {data.params.min_count}편 ·{' '}
            {data.params.correction_id === 'none' ? '보정 없음' : '보정 적용'}.
            아래는 마지막 계산 결과입니다.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>지표</th>
                  <th>기본 설정</th>
                  <th>변경 설정</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['tp', 'TP'],
                  ['fp', '실험상 FP'],
                  ['fn', 'FN'],
                  ['precision', 'Precision'],
                  ['recall', 'Recall'],
                  ['f1', 'F1'],
                  ['delay_mean', '평균 지연(년)'],
                  ['decoy_fp', '미끼 탐지'],
                ].map(([key, label]) => (
                  <tr key={key}>
                    <th>{label}</th>
                    <td>{display(key, data.reference_metrics[key])}</td>
                    <td>{display(key, data.metrics[key])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="view-note">
            주입 정답표에 없는 탐지를 실험상 FP로 셉니다. 원본 시나리오의
            Recall은 정답이 없어 계산할 수 없습니다.
          </p>
          {[
            ['added', '추가된 탐지'],
            ['removed', '해제된 탐지'],
          ].map(([kind, label]) => (
            <details key={kind}>
              <summary>
                {label} · {data[`${kind}_total`]}건
              </summary>
              {!data[kind].length ? (
                <p>해당 결과가 없습니다.</p>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>연도</th>
                        <th>기관 쌍</th>
                        <th>분야</th>
                        <th>점수</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data[kind].map((d, i) => (
                        <tr
                          key={`${d.domestic_id}:${d.foreign_id}:${d.field}:${d.year}:${i}`}
                        >
                          <th>{d.year}</th>
                          <td>
                            <button
                              className="pair-link"
                              onClick={() => onSelect(d)}
                            >
                              {d.domestic_name} / {d.foreign_name}
                            </button>
                          </td>
                          <td>{d.field}</td>
                          <td>{Number(d.score).toFixed(3)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {data[kind].length < data[`${kind}_total`] && (
                <p>처음 {data[kind].length}건만 표시합니다.</p>
              )}
            </details>
          ))}
          <p className="view-note">
            기관 쌍을 누르면 원본 타임라인으로 이동합니다. What-if 설정은 위
            표의 재계산 결과에 적용됩니다.
          </p>
        </>
      )}
    </section>
  )
}
