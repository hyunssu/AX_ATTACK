export default function ConfirmModal({ onConfirm, onClose }) {
  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h3 className="panel__title">신규단어를 등록하시겠습니까?</h3>
        <div className="modal-actions" style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '20px' }}>
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            아니오
          </button>
          <button type="button" className="btn btn--primary" onClick={onConfirm}>
            예
          </button>
        </div>
      </div>
    </div>
  )
}