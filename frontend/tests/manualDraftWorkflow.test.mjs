import assert from 'node:assert/strict'
import test from 'node:test'
import { createManualDraftWorkflow } from '../src/manualDraftWorkflow.js'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

test('deployment waits for an in-flight autosave and the final save', async () => {
  const started = deferred()
  const gate = deferred()
  const events = []
  const workflow = createManualDraftWorkflow(async content => {
    events.push(`save ${content}`)
    if (content === 'old') {
      started.resolve()
      await gate.promise
    }
    events.push(`saved ${content}`)
  })
  const autosave = workflow.save('old')
  await started.promise
  assert.equal(workflow.begin(), true)
  const deploy = workflow.save('latest').then(() => events.push('deploy'))
  assert.deepEqual(events, ['save old'])
  assert.equal(workflow.busy, true)
  gate.resolve()
  await Promise.all([autosave, deploy])
  assert.deepEqual(events, ['save old', 'saved old', 'save latest', 'saved latest', 'deploy'])
  workflow.end()
  assert.equal(workflow.busy, false)
})

test('begin blocks duplicate actions immediately, before a render', () => {
  const workflow = createManualDraftWorkflow(async () => {})
  assert.equal(workflow.begin(), true)
  assert.equal(workflow.begin(), false)
  workflow.end()
  assert.equal(workflow.begin(), true)
})

test('an earlier failed save does not prevent retrying the latest content', async () => {
  const calls = []
  const workflow = createManualDraftWorkflow(async content => {
    calls.push(content)
    if (content === 'old') throw new Error('Old save failed')
    return { ok: true }
  })
  await assert.rejects(workflow.save('old'), /Old save failed/)
  assert.equal((await workflow.save('latest')).ok, true)
  assert.deepEqual(calls, ['old', 'latest'])
})

test('failure of the final save prevents deployment', async () => {
  let deployed = false
  const workflow = createManualDraftWorkflow(async () => { throw new Error('Save failed') })
  await assert.rejects(workflow.save('latest').then(() => { deployed = true }), /Save failed/)
  assert.equal(deployed, false)
})

test('overlapping saves persist the latest snapshot last', async () => {
  const stored = []
  const workflow = createManualDraftWorkflow(async content => {
    await Promise.resolve()
    stored.push(content)
  })
  await Promise.all([workflow.save('first'), workflow.save('second'), workflow.save('latest')])
  assert.deepEqual(stored, ['first', 'second', 'latest'])
})

test('different manuals do not share their save queue or busy state', async () => {
  const gate = deferred()
  const first = createManualDraftWorkflow(() => gate.promise)
  const second = createManualDraftWorkflow(async () => 'saved')
  const pending = first.save('first manual')
  first.begin()
  assert.equal(second.busy, false)
  assert.equal(await second.save('second manual'), 'saved')
  gate.resolve()
  await pending
})
