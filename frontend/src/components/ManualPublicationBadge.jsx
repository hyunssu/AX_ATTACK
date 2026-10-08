import { TriangleAlert } from 'lucide-react'
import { getManualPublication } from '../manualPublication'
import './ManualPublicationBadge.css'

export default function ManualPublicationBadge({ manual }) {
  const { version, isPublished } = getManualPublication(manual)
  const description = isPublished ? `운영반영된 버전 v${version}` : '운영반영 필요: 아직 운영반영되지 않은 초안'

  return (
    <span
      className={`manual-publication-badge manual-publication-badge--${isPublished ? 'published' : 'draft'}`}
      title={description}
      aria-label={description}
    >
      {!isPublished && <TriangleAlert size={12} aria-hidden="true" />}
      {isPublished ? `v${version}` : '초안'}
    </span>
  )
}
