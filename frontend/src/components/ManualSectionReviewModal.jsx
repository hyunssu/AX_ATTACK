import ManualSectionReviewList from './ManualSectionReviewList'

export default function ManualSectionReviewModal({ sections, onChange, onConfirm, onCancel, confirming, error }) {
  const includedCount = sections.filter((s) => s.include).length

  return (
    <div className="modal-overlay">
      <div className="modal-card modal-card--xl">
        <h3 className="panel__title">분석 결과 확인</h3>
        <ManualSectionReviewList sections={sections} onChange={onChange} />
        {error && <div className="status-text">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="btn btn--ghost" onClick={onCancel} disabled={confirming}>취소</button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={onConfirm}
            disabled={confirming || includedCount === 0}
          >
            {confirming ? '등록 중…' : `확인 및 등록 (${includedCount}건)`}
          </button>
        </div>
      </div>
    </div>
  )
}
