import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { getData, getInstitutions } from '../src/api/client.js'

const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })

test('returns JSON and forwards the cancellation signal', async () => {
  const controller = new AbortController()
  globalThis.fetch = async (path, options) => {
    assert.equal(path, '/api/meta')
    assert.equal(options.signal, controller.signal)
    return Response.json({ data_version: 'example' })
  }
  assert.deepEqual(await getData('/api/meta', controller.signal), { data_version: 'example' })
})

test('preserves structured API error and HTTP status', async () => {
  globalThis.fetch = async () => Response.json(
    { error: { message: '해당 기관 쌍의 자료가 없습니다.' } }, { status: 404 },
  )
  await assert.rejects(getData('/api/timeline'), {
    message: '해당 기관 쌍의 자료가 없습니다.', status: 404,
  })
})

test('uses a fallback for an HTTP error without a message', async () => {
  globalThis.fetch = async () => Response.json({}, { status: 503 })
  await assert.rejects(getData('/api/meta'), {
    message: '데이터를 불러오지 못했습니다.', status: 503,
  })
})

test('HTML gateway failures show a readable error with status', async () => {
  globalThis.fetch = async () => new Response('<html>gateway failure</html>', { status: 503 })
  await assert.rejects(getData('/api/meta'), {
    message: '데이터를 불러오지 못했습니다. (HTTP 503)', status: 503,
  })
})

test('rejects an invalid JSON success response', async () => {
  globalThis.fetch = async () => new Response('not JSON')
  await assert.rejects(getData('/api/meta'), {
    message: '서버 응답이 올바른 JSON 형식이 아닙니다.', status: 200,
  })
})

test('does not convert a cancelled fetch into a visible API failure', async () => {
  const error = new DOMException('cancelled', 'AbortError')
  globalThis.fetch = async () => { throw error }
  await assert.rejects(getData('/api/meta'), (actual) => actual === error)
})

test('does not convert a cancelled body read into a JSON failure', async () => {
  const error = new DOMException('cancelled', 'AbortError')
  globalThis.fetch = async () => ({ json: async () => { throw error } })
  await assert.rejects(getData('/api/meta'), (actual) => actual === error)
})

test('preserves network failures for the caller to handle', async () => {
  const error = new TypeError('network unavailable')
  globalThis.fetch = async () => { throw error }
  await assert.rejects(getData('/api/meta'), (actual) => actual === error)
})


test('loads both pages of a large institution catalog', async () => {
  const first = Array.from({ length: 1000 }, (_, id) => ({ id: String(id) }))
  const last = [{ id: '1000' }]
  const controller = new AbortController()
  const offsets = []
  globalThis.fetch = async (path, { signal }) => {
    assert.equal(signal, controller.signal)
    const offset = new URL(path, 'http://localhost').searchParams.get('offset')
    offsets.push(offset)
    return Response.json({
      data_version: 'period', total: 1001, offset: Number(offset),
      items: offset == null ? first : last,
      next_offset: offset == null ? 1000 : null,
    })
  }
  const result = await getInstitutions('foreign', controller.signal)
  assert.deepEqual(offsets, [null, '1000'])
  assert.equal(result.count, 1001)
  assert.deepEqual(result.items.at(-1), last[0])
})

test('rejects institution pages from different data versions', async () => {
  globalThis.fetch = async (path) => {
    const offset = new URL(path, 'http://localhost').searchParams.get('offset')
    return Response.json({
      data_version: offset == null ? 'before' : 'after',
      total: 2, offset: Number(offset), items: [{ id: offset || '0' }],
      next_offset: offset == null ? 1 : null,
    })
  }
  await assert.rejects(getInstitutions('foreign'), /데이터가 갱신/)
})
