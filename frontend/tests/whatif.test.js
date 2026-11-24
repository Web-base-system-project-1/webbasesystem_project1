import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'
import { defaultSettings, postWhatIf } from '../src/api/whatif.js'

const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })

test('posts settings with cancellation and accepts the current data version', async () => {
  const controller = new AbortController()
  const settings = defaultSettings('growth')
  globalThis.fetch = async (path, options) => {
    assert.equal(path, '/api/whatif')
    assert.equal(options.method, 'POST')
    assert.equal(options.signal, controller.signal)
    assert.deepEqual(JSON.parse(options.body), settings)
    return Response.json({ data_version: 'current', counts: { removed: 57 } })
  }
  const result = await postWhatIf(settings, controller.signal, 'current')
  assert.equal(result.counts.removed, 57)
})

test('rejects a What-if result from a changed data version', async () => {
  globalThis.fetch = async () => Response.json({ data_version: 'new' })
  await assert.rejects(postWhatIf(defaultSettings(), undefined, 'old'), /데이터가 바뀌/)
})

test('preserves structured What-if failures and cancellation', async () => {
  globalThis.fetch = async () => Response.json({
    error: { code: 'invalid_parameter', message: 'k 범위를 확인하세요.' },
  }, { status: 400 })
  await assert.rejects(postWhatIf(defaultSettings()), {
    message: 'k 범위를 확인하세요.', code: 'invalid_parameter', status: 400,
  })
  const aborted = new DOMException('cancelled', 'AbortError')
  globalThis.fetch = async () => ({ json: async () => { throw aborted } })
  await assert.rejects(postWhatIf(defaultSettings()), (actual) => actual === aborted)
})
