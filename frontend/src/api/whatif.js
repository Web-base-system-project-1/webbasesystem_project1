// POST /api/whatif의 응답과 현재 데이터 버전을 확인한다.

export const DEFAULT_THRESHOLDS = { zscore: 2.5, growth: 1.0 }
export const CORRECTION_RULES = {
  zscore: 'min_international_total_3',
  growth: 'require_share_increase',
}

export function defaultSettings(detector = 'zscore') {
  return {
    detector,
    threshold: DEFAULT_THRESHOLDS[detector],
    k: 3,
    min_count: 3,
    scenario_id: 'original',
    correction_id: 'none',
    limit: 20,
  }
}

export async function postWhatIf(settings, signal, expectedVersion) {
  const response = await fetch('/api/whatif', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
    signal,
  })
  let body
  try {
    body = await response.json()
  } catch (cause) {
    if (cause.name === 'AbortError') throw cause
    const error = new Error(
      response.ok
        ? '서버 응답이 올바른 JSON 형식이 아닙니다.'
        : `다시 계산하지 못했습니다. (HTTP ${response.status})`,
    )
    error.status = response.status
    throw error
  }
  if (!response.ok) {
    const error = new Error(
      body.error?.message || '다시 계산하지 못했습니다.',
    )
    error.status = response.status
    error.code = body.error?.code
    throw error
  }
  if (expectedVersion && body.data_version !== expectedVersion)
    throw new Error('데이터가 바뀌었습니다. 새로고침해 주세요.')
  return body
}
