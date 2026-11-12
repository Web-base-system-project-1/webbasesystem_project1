export async function getData(path, signal) {
  const response = await fetch(path, { signal })
  let body
  try {
    body = await response.json()
  } catch (cause) {
    if (cause.name === 'AbortError') throw cause
    const error = new Error(
      response.ok
        ? '서버 응답이 올바른 JSON 형식이 아닙니다.'
        : `데이터를 불러오지 못했습니다. (HTTP ${response.status})`,
    )
    error.status = response.status
    throw error
  }
  if (!response.ok) {
    const error = new Error(
      body.error?.message || '데이터를 불러오지 못했습니다.',
    )
    error.status = response.status
    throw error
  }
  return body
}

export async function getInstitutions(role, signal) {
  const query = new URLSearchParams({ role, limit: '1000' })
  const first = await getData(`/api/institutions?${query}`, signal)
  const items = [...first.items]
  let page = first
  while (page.next_offset != null) {
    const offset = items.length
    if (page.next_offset !== offset || !page.items.length) {
      throw new Error('기관 목록의 다음 페이지 정보가 올바르지 않습니다.')
    }
    query.set('offset', String(offset))
    page = await getData(`/api/institutions?${query}`, signal)
    if (page.data_version !== first.data_version || page.total !== first.total) {
      throw new Error('데이터가 갱신되었습니다. 다시 불러와 주세요.')
    }
    if (page.offset !== offset || !page.items.length) {
      throw new Error('기관 목록의 다음 페이지를 불러오지 못했습니다.')
    }
    items.push(...page.items)
  }
  return { ...first, count: items.length, items }
}
