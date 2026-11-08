const number = new Intl.NumberFormat('ko-KR')

export default function YearlyTable({ points }) {
  return (
    <details>
      <summary>연도별 수치</summary>
      <div className="table-scroll">
        <table>
          <caption className="sr-only">
            선택한 기관 쌍의 연도별 공동논문 수와 협력 비중
          </caption>
          <thead>
            <tr>
              <th scope="col">연도</th>
              <th scope="col">공동논문 수</th>
              <th scope="col">국내 기관 국제 공동논문 수</th>
              <th scope="col">협력 비중</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.year}>
                <th scope="row">{p.year}</th>
                <td>
                  {p.collab_count == null ? '—' : number.format(p.collab_count)}
                </td>
                <td>
                  {p.international_total == null
                    ? '—'
                    : number.format(p.international_total)}
                </td>
                <td>
                  {p.share == null ? '—' : `${(p.share * 100).toFixed(1)}%`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
