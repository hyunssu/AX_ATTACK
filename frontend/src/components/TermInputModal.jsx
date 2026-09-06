import { useState } from 'react'

export default function TermInputModal({ onSubmit, onClose }) {
  const [termName, setTermName] = useState('')
  const [keyword, setKeyword] = useState('')
  const [definition, setDefinition] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!termName.trim() || !definition.trim()) {
      alert('단어명과 설명은 필수 입력 항목입니다.')
      return
    }
    onSubmit({ termName, keyword, definition })
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h3 className="panel__title">신규 단어 등록</h3>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '14px', fontWeight: '500' }}>신규단어</label>
            <input
              type="text"
              value={termName}
              onChange={(e) => setTermName(e.target.value)}
              placeholder="단어명을 입력하세요"
              style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '14px', fontWeight: '500' }}>동의어 및 약어</label>
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="동의어 또는 약어를 입력하세요 (선택)"
              style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '14px', fontWeight: '500' }}>설명</label>
            <textarea
              value={definition}
              onChange={(e) => setDefinition(e.target.value)}
              placeholder="단어의 정의를 입력하세요"
              rows={4}
              style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc', resize: 'vertical' }}
            />
          </div>

          <div className="modal-actions" style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '10px' }}>
            <button type="button" className="btn btn--secondary" onClick={onClose}>
              취소
            </button>
            <button type="submit" className="btn btn--primary">
              저장
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}