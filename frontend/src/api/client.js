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
