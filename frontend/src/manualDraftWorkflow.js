export function canVerifyManualDraft({ editable, hasChanges, draftStatus, busy }) {
  return Boolean(editable && !busy && (hasChanges || draftStatus === 'draft'))
}

export function createManualDraftWorkflow(saveDraft) {
  let queue = Promise.resolve()
  let busy = false

  return {
    get busy() {
      return busy
    },
    begin() {
      if (busy) return false
      busy = true
      return true
    },
    end() {
      busy = false
    },
    save(content) {
      // Drain earlier saves before verification or deployment can continue.
      queue = queue.catch(() => {}).then(() => saveDraft(content))
      return queue
    },
  }
}
