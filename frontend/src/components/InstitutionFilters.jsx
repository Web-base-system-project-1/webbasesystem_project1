const fields = {
  ai: 'AI',
  bio: '바이오',
  semiconductor: '반도체',
  quantum: '양자',
}

export default function InstitutionFilters({ catalog, selection, onChange }) {
  return (
    <section className="filters" aria-label="조회 조건">
      <label>
        국내 기관
        <select
          name="domestic_id"
          value={selection.domestic_id}
          onChange={onChange}
          disabled={!catalog}
        >
          {!catalog?.domestic.length && <option value="">기관 없음</option>}
          {catalog?.domestic.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        해외 기관
        <select
          name="foreign_id"
          value={selection.foreign_id}
          onChange={onChange}
          disabled={!catalog}
        >
          {!catalog?.foreign.length && <option value="">기관 없음</option>}
          {catalog?.foreign.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
              {item.country_code ? ` (${item.country_code})` : ''}
            </option>
          ))}
        </select>
      </label>
      <label className="field-filter">
        분야
        <select
          name="field"
          value={selection.field}
          onChange={onChange}
          disabled={!catalog}
        >
          {!catalog?.meta.fields.length && <option value="">분야 없음</option>}
          {catalog?.meta.fields.map((field) => (
            <option key={field} value={field}>
              {fields[field] || field}
            </option>
          ))}
        </select>
      </label>
    </section>
  )
}
