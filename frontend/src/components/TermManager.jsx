import { useState } from 'react'
import ConfirmModal from './TermConfirmModal'
import TermInputModal from './TermInputModal'

export default function TermManager() {
  const [modalStep, setModalStep] = useState(null)

  const handleSubmit = async (data) => {
    try {
      const response = await fetch('/api/terms/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          term_name: data.termName,
          keyword: data.keyword,
          definition: data.definition,
          category: data.category,
        }),
      })

      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.detail || '단어 등록에 실패했습니다.')
      }

      console.log('등록 성공:', result)

      alert(`단어가 등록되었습니다. (ID: ${result.term_id})`)
      setModalStep(null)

    } catch (error) {
      console.error('단어 등록 실패:', error)
      alert(`단어 등록에 실패했습니다.\n${error.message}`)
    }
  }

  return (
    <div>
      <button
        className="btn btn--primary qa-sidebar__new"
        onClick={() => setModalStep('confirm')}
      >
        + 신규단어 등록
      </button>

      {modalStep === 'confirm' && (
        <ConfirmModal
          onConfirm={() => setModalStep('input')}
          onClose={() => setModalStep(null)}
        />
      )}

      {modalStep === 'input' && (
        <TermInputModal
          onSubmit={handleSubmit}
          onClose={() => setModalStep(null)}
        />
      )}
    </div>
  )
}