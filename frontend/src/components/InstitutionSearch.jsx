import { useEffect, useState } from 'react'
import { getData } from '../api/client'

export default function InstitutionSearch({
  role,
  label,
  value,
  name,
  selectedName,
  version,
  onChange,
  field,
  relatedId,
}) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const key = JSON.stringify([role, query, version, field, relatedId])
  const current = result?.key === key ? result : null
  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => {
      getData(
        `/api/institutions?${new URLSearchParams({
          role,
          q: query,
          limit: '100',
          field,
          ...(relatedId
            ? { [role === 'foreign' ? 'domestic_id' : 'foreign_id']: relatedId }
            : {}),
        })}`,
        controller.signal,
      )
        .then((data) => {
          if (data.data_version !== version)
            throw new Error('데이터가 변경되었습니다. 새로고침해 주세요.')
          if (!controller.signal.aborted) setResult({ key, data })
        })
        .catch((error) => {
          if (!controller.signal.aborted)
            setResult({ key, error: error.message })
        })
    }, 200)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [role, query, version, field, relatedId, key])
  const items = current?.data?.items || []
  return (
    <div className="institution-search">
      <label>
        {label} 검색
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="기관명 또는 ID"
        />
      </label>
      <label>
        {label}
        <select name={name} value={value} onChange={onChange}>
          <option value="">전체 · 선택 해제</option>
          {value && !items.some((item) => item.id === value) && (
            <option value={value}>
              {selectedName || value || '기관 선택'}
            </option>
          )}
          {items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
              {item.country_code ? ` (${item.country_code})` : ''}
            </option>
          ))}
        </select>
      </label>
      <small role="status">
        {current?.error ||
          (!current
            ? '검색 중…'
            : `${current.data.count} / ${current.data.total}곳 · 협력 데이터가 있는 기관`)}
      </small>
    </div>
  )
}
