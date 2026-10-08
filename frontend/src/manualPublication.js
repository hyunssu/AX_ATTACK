export function getManualPublication(manual) {
  const value = Number(manual?.latest_done_version_no)
  const version = Number.isInteger(value) && value >= 1 ? value : null
  return { version, isPublished: version !== null }
}

export function isPublishedManualEditing(manual, lockedBy = manual?.locked_by) {
  return getManualPublication(manual).isPublished && Boolean(lockedBy)
}
