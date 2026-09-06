import { useState } from 'react'
import ConfirmModal from './TermConfirmModal'
import TermInputModal from './TermInputModal'

export default function TermManager() {
  const [modalStep, setModalStep] = useState(null) // null, 'confirm', 'input'

  return (
    <div>
      <button className="btn btn--primary" onClick={() => setModalStep('confirm')}>
        단어 등록하기
      </button>

      {/* 1. 등록 여부 확인 팝업 */}
      {modalStep === 'confirm' && (
        <ConfirmModal
          onConfirm={() => setModalStep('input')} // '예' 누르면 입력 팝업으로 이동
          onClose={() => setModalStep(null)}     // '아니오' 누르면 팝업 닫기
        />
      )}

      {/* 2. 상세 정보 입력 팝업 */}
      {modalStep === 'input' && (
        <TermInputModal
          onSubmit={(data) => {
            console.log('저장할 데이터:', data)
            // TODO: API 호출 등 저장 로직 처리
            setModalStep(null)
          }}
          onClose={() => setModalStep(null)}
        />
      )}
    </div>
  )
}