import { useEffect, useState } from 'react'
import { getData } from './api/client'
import InstitutionFilters from './components/InstitutionFilters'
import TimelineChart from './components/TimelineChart'
import TimelineSummary from './components/TimelineSummary'
import YearlyTable from './components/YearlyTable'
import DetectionList from './components/DetectionList'
import './App.css'

function App() {
  const [catalog, setCatalog] = useState(null)
  const [selection, setSelection] = useState({
    domestic_id: '',
    foreign_id: '',
    field: '',
  })
  const [timeline, setTimeline] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [empty, setEmpty] = useState(false)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    setCatalog(null)
    setTimeline(null)
    Promise.all(
      [
        '/api/meta',
        '/api/institutions?role=domestic&limit=1000',
        '/api/institutions?role=foreign&limit=1000',
        '/api/pairs?limit=1',
      ].map((path) => getData(path, controller.signal)),
    )
      .then(([meta, domestic, foreign, pairs]) => {
        if (
          [domestic, foreign, pairs].some(
            (data) => data.data_version !== meta.data_version,
          )
        )
          throw new Error('데이터가 갱신되었습니다. 다시 불러와 주세요.')
        if (domestic.count < domestic.total || foreign.count < foreign.total)
          throw new Error(
            '기관 목록을 모두 불러올 수 없습니다. 검색 API 연결이 필요합니다.',
          )
        const first = pairs.items[0]
        setCatalog({ meta, domestic: domestic.items, foreign: foreign.items })
        setSelection({
          domestic_id: first?.domestic_id || domestic.items[0]?.id || '',
          foreign_id: first?.foreign_id || foreign.items[0]?.id || '',
          field: first?.field || meta.fields[0] || '',
        })
        setLoading(false)
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message)
          setLoading(false)
        }
      })
    return () => controller.abort()
  }, [retry])

  useEffect(() => {
    if (!catalog || Object.values(selection).some((value) => !value)) return
    const controller = new AbortController()
    setLoading(true)
    setError('')
    setEmpty(false)
    setTimeline(null)
    getData(
      `/api/timeline?${new URLSearchParams(selection)}`,
      controller.signal,
    )
      .then((data) => {
        if (data.data_version !== catalog.meta.data_version)
          throw new Error('데이터가 갱신되었습니다. 다시 불러와 주세요.')
        setTimeline({
          ...data,
          points: [...data.points].sort((a, b) => a.year - b.year),
        })
        setEmpty(!data.points.length)
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          if (err.status === 404) setEmpty(true)
          else setError(err.message)
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [catalog, selection])

  const points = timeline?.points || []
  const change = (event) =>
    setSelection((previous) => ({
      ...previous,
      [event.target.name]: event.target.value,
    }))
  const noSelection =
    catalog && Object.values(selection).some((value) => !value)

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
            {catalog.meta.years.min}–{catalog.meta.years.max}
          </span>
        )}
      </header>

      <InstitutionFilters
        catalog={catalog}
        selection={selection}
        onChange={change}
      />

      <section className="results" aria-label="조회 결과" aria-busy={loading}>
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
            선택한 조건의 데이터가 없습니다. 다른 기관이나 분야를 선택해 주세요.
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
                <TimelineChart points={points} />
              </div>
              <YearlyTable points={points} />
              <DetectionList
                detections={timeline.detections || []}
                pair={timeline.pair}
              />
            </>
          )
        )}
      </section>
      <footer>
        {catalog?.meta.is_real_data === false
          ? '화면 확인을 위한 예시 데이터입니다. 실제 연구 실적과 다릅니다.'
          : '협력 비중은 국내 기관의 국제 공동논문 중 해당 해외 기관과 함께 쓴 논문의 비율입니다.'}
      </footer>
    </main>
  )
}

export default App
