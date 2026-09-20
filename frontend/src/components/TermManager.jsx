import { useEffect, useState } from 'react'
import ConfirmModal from './TermConfirmModal'
import TermInputModal from './TermInputModal'

export default function TermManager({
  initialTermName = '',
  autoOpen = false,
  onRegistered,
  onDeclined,
  buttonLabel = '+ 신규단어 등록',
}) {
  const [modalStep, setModalStep] = useState(null)

  useEffect(() => {
    if (autoOpen) setModalStep('confirm')
  }, [autoOpen, initialTermName])

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

      setModalStep(null)
      if (onRegistered) {
        await onRegistered(result)
      } else {
        alert(`단어가 등록되었습니다. (ID: ${result.term_id})`)
      }

    } catch (error) {
      console.error('단어 등록 실패:', error)
      alert(`단어 등록에 실패했습니다.\n${error.message}`)
    }
  }

  const handleDecline = async () => {
    setModalStep(null)
    if (onDeclined) await onDeclined()
  }

  return (
    <div>
      <button
        className="btn btn--primary qa-sidebar__new"
        onClick={() => setModalStep('confirm')}
      >
        {buttonLabel}
      </button>

      {modalStep === 'confirm' && (
        <ConfirmModal
          onConfirm={() => setModalStep('input')}
          onClose={handleDecline}
        />
      )}

      {modalStep === 'input' && (
        <TermInputModal
          onSubmit={handleSubmit}
          onClose={() => setModalStep(null)}
          initialTermName={initialTermName}
        />
      )}
    </div>
  )
}
