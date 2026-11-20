import useApi from '../hooks/useApi'

export default function CooperationMatrix({
  selection,
  year,
  type,
  country,
  version,
  onSelect,
}) {
  const query = new URLSearchParams({
    ...selection,
    source: 'live',
    limit: '15',
  })
  if (year) query.set('year', year)
  if (type) query.set('type', type)
  if (country) query.set('country', country)
  const { data, error, reload } = useApi(`/api/matrix?${query}`, version)
  if (error)
    return (
      <p role="alert">
        {error} <button onClick={reload}>다시 불러오기</button>
      </p>
    )
  if (!data) return <p role="status">협력 관계를 불러오는 중입니다.</p>
  const cells = new Map(
    data.items.map((r) => [`${r.domestic_id}:${r.foreign_id}`, r]),
  )
  return (
    <section aria-label="기관 협력 행렬">
      <h2>기관 협력 관계{country ? ` · ${country}` : ''}</h2>
      <p className="view-note">
        현재 분야·연도·기관·유형 조건의 공동논문 수입니다. 국내·해외 각각 건수
        상위 15곳까지 표시합니다. ●는 기본 탐지 조건에서 탐지가 있는 관계입니다.
        숫자를 누르면 타임라인으로 이동합니다.
      </p>
      {!data.items.length ? (
        <p role="status">
          선택한 조건의 협력 관계가 없습니다. 기관 선택이나 국가 조건을 해제해
          보세요.
        </p>
      ) : (
        <div className="table-scroll">
          <table className="matrix">
            <caption className="sr-only">
              국내 기관과 해외 기관 사이의 공동논문 수
            </caption>
            <thead>
              <tr>
                <th>국내 / 해외</th>
                {data.foreign.map((i) => (
                  <th key={i.id} title={i.name} scope="col">
                    {i.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.domestic.map((d) => (
                <tr key={d.id}>
                  <th scope="row">{d.name}</th>
                  {data.foreign.map((f) => {
                    const cell = cells.get(`${d.id}:${f.id}`)
                    return (
                      <td key={f.id}>
                        {cell ? (
                          <button
                            className="matrix-cell"
                            onClick={() =>
                              onSelect({
                                ...cell,
                                field: selection.field,
                                year: year ? Number(year) : null,
                              })
                            }
                            title={`${d.name} / ${f.name} · ${cell.collab_count}편 · 탐지 ${cell.detections}건`}
                          >
                            {cell.collab_count}
                            {cell.detections > 0 ? ' ●' : ''}
                          </button>
                        ) : (
                          '—'
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
      <p className="view-note">
        전체 {data.total_pairs}개 관계 중 {data.count}개 표시. 기관 쌍 건수는
        고유 논문 총수와 다릅니다.
      </p>
    </section>
  )
}
