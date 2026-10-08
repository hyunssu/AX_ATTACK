import assert from 'node:assert/strict'
import test from 'node:test'
import { getManualPublication, isPublishedManualEditing } from '../src/manualPublication.js'

test('a completed version stays published while a newer draft is edited', () => {
  assert.deepEqual(getManualPublication({ latest_done_version_no: 1, latest_draft_index_step: 'draft', version_count: 2 }),
    { version: 1, isPublished: true })
})

test('the first saved version is still a draft until deployment completes', () => {
  assert.deepEqual(getManualPublication({ latest_done_version_no: null, latest_draft_index_step: 'draft', version_count: 1 }),
    { version: null, isPublished: false })
})

test('the displayed version follows completed deployments, not draft counts', () => {
  assert.deepEqual(getManualPublication({ latest_done_version_no: 3, latest_draft_index_step: 'embedding', version_count: 4 }),
    { version: 3, isPublished: true })
})

test('positive integer version strings are supported', () => {
  assert.deepEqual(getManualPublication({ latest_done_version_no: '12' }), { version: 12, isPublished: true })
})

test('missing or invalid published versions stay unpublished', () => {
  for (const latest_done_version_no of [undefined, null, 0, -1, '', 'draft', 1.5]) {
    assert.deepEqual(getManualPublication({ latest_done_version_no }), { version: null, isPublished: false })
  }
  assert.deepEqual(getManualPublication(), { version: null, isPublished: false })
})

test('a published manual locked by any editor shows editing status', () => {
  for (const locked_by of ['current-user', 'another-user']) {
    assert.equal(isPublishedManualEditing({ latest_done_version_no: 1, locked_by }), true)
  }
})

test('an unlocked published manual does not show editing status for a saved draft alone', () => {
  assert.equal(isPublishedManualEditing({ latest_done_version_no: 1, latest_draft_index_step: 'draft', locked_by: null }), false)
})

test('an initial draft keeps draft labels instead of published editing status', () => {
  assert.equal(isPublishedManualEditing({ latest_done_version_no: null, locked_by: 'current-user' }), false)
})

test('the current lock state overrides stale list data when locking and unlocking', () => {
  assert.equal(isPublishedManualEditing({ latest_done_version_no: 2, locked_by: null }, 'current-user'), true)
  assert.equal(isPublishedManualEditing({ latest_done_version_no: 2, locked_by: 'current-user' }, null), false)
})
