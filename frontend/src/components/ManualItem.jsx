const STEP_LABEL = {
  draft: '초안',
  converting: '변환 중',
  chunking: '청킹 중',
  embedding: '임베딩 중',
  error: '오류',
}

function StepBadge({ step }) {
  if (!step || step === 'done') return null
  const label = STEP_LABEL[step] ?? step
  const mod = step === 'draft' ? 'draft' : step === 'error' ? 'error' : 'indexing'
  return <span className={`step-badge step-badge--${mod}`}>{label}</span>
}

export default function ManualItem({ manual, onSelect, isFavorited, onToggleFavorite, currentUser }) {
  const doneVer = manual.latest_done_version_no
  const draftStep = manual.latest_draft_index_step
  const isLockedByMe = manual.locked_by && manual.locked_by === currentUser
  const isLockedByOther = manual.locked_by && manual.locked_by !== currentUser

  return (
    <div className="manual-card" role="button" tabIndex={0} onClick={onSelect}>
      <div className="manual-card__thumb" aria-hidden="true">{manual.title.charAt(0)}</div>
      <div className="manual-card__top">
        <div className="eyebrow">DOCUMENT</div>
        <div className="manual-card__top-right">
          {manual.lang_c && (
            <span className="manual-card__lang">{manual.lang_c.toUpperCase()}</span>
          )}
          {manual.categories?.map((cat) => (
            <span key={cat} className="manual-card__category">{cat}</span>
          ))}
          {onToggleFavorite && (
            <button
              className={`manual-card__fav${isFavorited ? ' manual-card__fav--on' : ''}`}
              title={isFavorited ? '즐겨찾기 해제' : '즐겨찾기 추가'}
              onClick={e => { e.stopPropagation(); onToggleFavorite() }}
            >
              {isFavorited ? '★' : '☆'}
            </button>
          )}
        </div>
      </div>
      <div className="manual-card__title">{manual.title}</div>
      <div className="manual-card__status">
        {doneVer != null && (
          <span className="step-badge step-badge--done">v{doneVer} 서비스 중</span>
        )}
        <StepBadge step={draftStep} />
        {doneVer == null && !draftStep && (
          <span className="step-badge step-badge--draft">버전 없음</span>
        )}
        {isLockedByMe && (
          <span className="step-badge step-badge--lock-me" title="내가 편집 중">🔒 편집 중</span>
        )}
        {isLockedByOther && (
          <span className="step-badge step-badge--lock-other" title={`${manual.locked_by}님이 편집 중`}>
            🔒 {manual.locked_by}
          </span>
        )}
      </div>
      <div className="manual-card__link">자세히 보기 →</div>
    </div>
  )
}
