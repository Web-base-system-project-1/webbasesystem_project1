import { useEffect, useState } from 'react'
import { getData } from '../api/client'

export default function useApi(path, version, body = null) {
  const [result, setResult] = useState(null)
  const [retry, setRetry] = useState(0)
  const key = JSON.stringify([path, version, retry, body])
  useEffect(() => {
    if (!path) return
    const controller = new AbortController()
    getData(
      path,
      controller.signal,
      body
        ? {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body,
          }
        : {},
    )
      .then((data) => {
        if (data.data_version !== version)
          throw new Error('데이터가 바뀌었습니다. 새로고침해 주세요.')
        if (!controller.signal.aborted) setResult({ key, data })
      })
      .catch((error) => {
        if (!controller.signal.aborted) setResult({ key, error: error.message })
      })
    return () => controller.abort()
  }, [path, version, key, body])
  return {
    ...(result?.key === key ? result : {}),
    reload: () => setRetry((v) => v + 1),
  }
}
