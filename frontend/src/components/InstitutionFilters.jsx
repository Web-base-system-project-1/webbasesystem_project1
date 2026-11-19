import InstitutionSearch from './InstitutionSearch'
const fields = {
  ai: 'AI',
  bio: '바이오',
  semiconductor: '반도체',
  quantum: '양자',
}

export default function InstitutionFilters({
  catalog,
  selection,
  onChange,
  pair,
}) {
  return (
    <section className="filters" aria-label="조회 조건">
      {catalog && (
        <>
          <InstitutionSearch
            role="domestic"
            field={selection.field}
            relatedId={selection.foreign_id}
            label="국내 기관"
            name="domestic_id"
            value={selection.domestic_id}
            selectedName={
              (pair?.domestic_id === selection.domestic_id
                ? pair.domestic_name
                : null) ||
              catalog.domestic.find((i) => i.id === selection.domestic_id)?.name
            }
            version={catalog.meta.data_version}
            onChange={onChange}
          />
          <InstitutionSearch
            role="foreign"
            field={selection.field}
            relatedId={selection.domestic_id}
            label="해외 기관"
            name="foreign_id"
            value={selection.foreign_id}
            selectedName={
              (pair?.foreign_id === selection.foreign_id
                ? pair.foreign_name
                : null) ||
              catalog.foreign.find((i) => i.id === selection.foreign_id)?.name
            }
            version={catalog.meta.data_version}
            onChange={onChange}
          />
        </>
      )}
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
