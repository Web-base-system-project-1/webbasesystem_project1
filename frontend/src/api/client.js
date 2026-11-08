export async function getData(path, signal) {
  const response = await fetch(path, { signal })
  const body = await response.json()
  if (!response.ok) {
    const error = new Error(
      body.error?.message || '데이터를 불러오지 못했습니다.',
    )
    error.status = response.status
    throw error
  }
  return body
}
