import { useEffect, useState } from 'react'
import { getData, getInstitutions } from './api/client'
import InstitutionFilters from './components/InstitutionFilters'
import TimelineChart from './components/TimelineChart'
import TimelineSummary from './components/TimelineSummary'
import YearlyTable from './components/YearlyTable'
import DetectionList from './components/DetectionList'
import ExperimentView from './components/ExperimentView'
import OverviewHeatmap from './components/OverviewHeatmap'
import CooperationMatrix from './components/CooperationMatrix'
import ShareTimeline from './components/ShareTimeline'
import CorrectionView from './components/CorrectionView'
import WhatIfView from './components/WhatIfView'
import './App.css'

function App() {
  const [view, setView] = useState('overview')
  const [year, setYear] = useState('')
  const [type, setType] = useState('')
  const [country, setCountry] = useState('')
  const [catalogResult, setCatalogResult] = useState(null)
  const [selection, setSelection] = useState({
    domestic_id: '',
    foreign_id: '',
    field: '',
  })
  const [timelineResult, setTimelineResult] = useState(null)
  const [selectedYear, setSelectedYear] = useState(null)
  const [retry, setRetry] = useState(0)
  const catalog = catalogResult?.retry === retry ? catalogResult.catalog : null
  const catalogError =
    catalogResult?.retry === retry ? catalogResult.error || '' : ''
  const noSelection =
    catalog && Object.values(selection).some((value) => !value)
  // 선택·데이터 버전이 바뀐 렌더부터 이전 결과를 숨깁니다.
  const result =
    timelineResult?.catalog === catalog &&
    timelineResult?.selection === selection
      ? timelineResult
      : null
  const timeline = result?.data
  const loading = !catalogError && (!catalog || (!noSelection && !result))
  const error = catalogError || result?.error || ''
  const empty = result?.empty || false

  useEffect(() => {
    const controller = new AbortController()
    Promise.all(
      [
        '/api/meta',
        getInstitutions('domestic', controller.signal),
        getInstitutions('foreign', controller.signal),
        '/api/pairs?limit=1',
        '/api/detections?source=live&limit=1000',
      ].map((path) =>
        typeof path === 'string' ? getData(path, controller.signal) : path,
      ),
    )
      .then(([meta, domestic, foreign, pairs, detections]) => {
        if (controller.signal.aborted) return
        if (
          [domestic, foreign, pairs, detections].some(
            (data) => data.data_version !== meta.data_version,
          )
        )
          throw new Error('데이터가 갱신되었습니다. 다시 불러와 주세요.')
        const first = pairs.items[0]
        setCatalogResult({
          retry,
          catalog: {
            meta,
            domestic: domestic.items,
            foreign: foreign.items,
            detections,
          },
        })
        setSelection({
          domestic_id: first?.domestic_id || domestic.items[0]?.id || '',
          foreign_id: first?.foreign_id || foreign.items[0]?.id || '',
          field: first?.field || meta.fields[0] || '',
        })
      })
      .catch((err) => {
        if (err.name !== 'AbortError' && !controller.signal.aborted)
          setCatalogResult({ retry, error: err.message })
      })
    return () => controller.abort()
  }, [retry])

  useEffect(() => {
    if (!catalog || Object.values(selection).some((value) => !value)) return
    const controller = new AbortController()
    getData(
      `/api/timeline?${new URLSearchParams({ ...selection, source: 'live' })}`,
      controller.signal,
    )
      .then((data) => {
        if (controller.signal.aborted) return
        if (data.data_version !== catalog.meta.data_version)
          throw new Error('데이터가 갱신되었습니다. 다시 불러와 주세요.')
        setTimelineResult({
          catalog,
          selection,
          data: {
            ...data,
            points: [...data.points].sort((a, b) => a.year - b.year),
          },
          empty: !data.points.length,
        })
      })
      .catch((err) => {
        if (err.name !== 'AbortError' && !controller.signal.aborted)
          setTimelineResult({
            catalog,
            selection,
            empty: err.status === 404,
            error: err.status === 404 ? '' : err.message,
          })
      })
    return () => controller.abort()
  }, [catalog, selection])

  const points = timeline?.points || []
  const change = (event) => {
    const { name, value } = event.target
    setSelectedYear(null)
    setSelection((previous) => ({
      ...previous,
      ...(name === 'field' ? { domestic_id: '', foreign_id: '' } : {}),
      [name]: value,
    }))
  }
  const selectDetection = (row) => {
    setView('timeline')
    setYear(row.year == null ? '' : String(row.year))
    setCountry('')
    setSelection({
      domestic_id: row.domestic_id,
      foreign_id: row.foreign_id,
      field: row.field,
    })
    setSelectedYear(row.year)
    document.getElementById('timeline')?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <main>
      <header className="page-header">
        <div>
          <p className="eyebrow">국제 공동연구</p>
          <h1>기관별 협력 추이</h1>
        </div>
        {catalog && (
          <span className="data-note">
            {catalog.meta.is_real_data ? '수집 데이터' : '예시 데이터'}
            <span className="note-dot">·</span>
            {catalog.meta.years.min == null
              ? '기간 정보 없음'
              : `${catalog.meta.years.min}–${catalog.meta.years.max}`}
          </span>
        )}
      </header>

      <nav className="view-tabs" aria-label="분석 화면">
        {[
          ['overview', '국가 개요'],
          ['matrix', '협력 관계'],
          ['timeline', '기관 추이'],
          ['detections', '탐지 결과'],
          ['experiment', '주입 실험'],
          ['corrections', '보정 비교'],
          ['whatif', 'What-if'],
        ].map(([id, label]) => (
          <button
            key={id}
            aria-pressed={view === id}
            onClick={() => setView(id)}
          >
            {label}
          </button>
        ))}
      </nav>
      <div className="scope-filters">
        <label>
          연도
          <select
            value={year}
            onChange={(e) => {
              setYear(e.target.value)
              setSelectedYear(e.target.value ? Number(e.target.value) : null)
            }}
          >
            <option value="">전체 기간</option>
            {catalog?.meta.years.min != null &&
              Array.from(
                { length: catalog.meta.years.max - catalog.meta.years.min + 1 },
                (_, i) => catalog.meta.years.min + i,
              ).map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
          </select>
        </label>
        <label>
          국내 기관 유형
          <select
            value={type}
            onChange={(e) => {
              setType(e.target.value)
              setSelection((p) => ({ ...p, domestic_id: '', foreign_id: '' }))
              setSelectedYear(null)
            }}
          >
            <option value="">전체 유형</option>
            <option value="education">대학·교육기관</option>
            <option value="facility">연구시설</option>
            <option value="government">정부기관</option>
          </select>
        </label>
        <button
          className="plain-button"
          onClick={() => {
            setSelection((p) => ({ ...p, domestic_id: '', foreign_id: '' }))
            setSelectedYear(null)
          }}
        >
          기관 선택 해제
        </button>
        {country && (
          <button className="plain-button" onClick={() => setCountry('')}>
            국가 조건 해제 · {country}
          </button>
        )}
      </div>
      {!catalog && !catalogError && <p role="status">데이터를 불러오는 중입니다.</p>}
      {catalogError && view !== 'timeline' && (
        <p role="alert">
          {catalogError}{' '}
          <button onClick={() => setRetry((v) => v + 1)}>다시 불러오기</button>
        </p>
      )}
      <InstitutionFilters
        catalog={catalog}
        selection={selection}
        pair={timeline?.pair}
        year={year}
        type={type}
        onChange={change}
      />

      {catalog && view === 'overview' && (
        <OverviewHeatmap
          field={selection.field}
          year={year}
          version={catalog.meta.data_version}
          onCountry={(code, y) => {
            setCountry(code || '')
            setYear(String(y))
            setSelection((p) => ({ ...p, domestic_id: '', foreign_id: '' }))
            setView('matrix')
          }}
        />
      )}
      {catalog && view === 'matrix' && (
        <CooperationMatrix
          selection={selection}
          year={year}
          type={type}
          country={country}
          version={catalog.meta.data_version}
          onSelect={selectDetection}
        />
      )}
      <section
        hidden={view !== 'timeline'}
        id="timeline"
        className="results"
        aria-label="조회 결과"
        aria-busy={loading}
      >
        {loading ? (
          <div className="state" role="status">
            데이터를 불러오는 중입니다.
          </div>
        ) : error ? (
          <div className="state" role="alert">
            <p>{error}</p>
            <button onClick={() => setRetry((value) => value + 1)}>
              다시 불러오기
            </button>
          </div>
        ) : empty || noSelection ? (
          <div className="state" role="status">
            {noSelection
              ? '국내 기관과 해외 기관을 선택해 주세요. 어느 쪽부터 선택해도 됩니다.'
              : '선택한 조건의 데이터가 없습니다. 다른 기관이나 분야를 선택해 주세요.'}
          </div>
        ) : (
          timeline && (
            <>
              <div className="chart-heading">
                <div>
                  <h2>연도별 공동논문 수</h2>
                  <p>
                    {timeline.pair.domestic_name}{' '}
                    <span className="pair-divider">/</span>{' '}
                    {timeline.pair.foreign_name}
                  </p>
                </div>
                <span className="unit">단위: 편</span>
              </div>
              <TimelineSummary points={points} />
              <div className="chart-scroll">
                <TimelineChart points={points} selectedYear={selectedYear} />
              </div>
              <p className="view-note">
                타임라인은 과거 기준을 확인할 수 있도록 전체 기간을 표시하며,
                선택한 연도를 강조합니다.
              </p>
              <ShareTimeline
                points={points}
                baseline={timeline.baseline || []}
                detections={timeline.detections || []}
                injections={timeline.injections || []}
                selectedYear={selectedYear}
              />
              <YearlyTable points={points} />
              {selectedYear && (
                <p role="status">선택한 탐지 연도: {selectedYear}년</p>
              )}
            </>
          )
        )}
      </section>
      {catalog && view === 'detections' && (
        <>
          {catalog.meta.is_real_data && (
            <p className="detection-note">
              각 분야 하위 토픽의 실제 수집 검증 데이터입니다. 전체 분야를
              대표하지 않으며, 원본 탐지는 이상 여부가 확정된 판정이 아닙니다.
            </p>
          )}
          <DetectionList
            detections={catalog.detections.items.filter(
              (d) =>
                (!selection.field || d.field === selection.field) &&
                (!selection.domestic_id ||
                  d.domestic_id === selection.domestic_id) &&
                (!selection.foreign_id ||
                  d.foreign_id === selection.foreign_id) &&
                (!year || d.year === Number(year)) &&
                (!type ||
                  catalog.domestic.some(
                    (i) => i.id === d.domestic_id && i.type === type,
                  )),
            )}
            onSelect={selectDetection}
          />
          {catalog.detections.count < catalog.detections.total && (
            <p>
              전체 {catalog.detections.total}건 중 {catalog.detections.count}건
              표시
            </p>
          )}
        </>
      )}
      {catalog && view === 'experiment' && (
        <ExperimentView
          selection={selection}
          version={catalog.meta.data_version}
          onSelect={selectDetection}
        />
      )}
      {catalog && view === 'corrections' && (
        <CorrectionView
          selection={selection}
          version={catalog.meta.data_version}
          onSelect={selectDetection}
        />
      )}
      {catalog && view === 'whatif' && (
        <WhatIfView
          version={catalog.meta.data_version}
          onSelect={selectDetection}
        />
      )}
      <footer>
        {catalog?.meta.is_real_data === false
          ? '화면 확인을 위한 예시 데이터입니다. 실제 연구 실적과 다릅니다.'
          : '협력 비중은 국내 기관의 국제 공동논문 중 해당 해외 기관과 함께 쓴 논문의 비율입니다.'}
      </footer>
    </main>
  )
}

export default App
