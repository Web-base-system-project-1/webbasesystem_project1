import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { getData } from '../src/api/client.js'

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
