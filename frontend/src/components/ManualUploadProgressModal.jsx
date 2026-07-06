import { useEffect, useRef, useState } from 'react'
import { fetchUploadJobStatus } from '../api'

const STEPS = [
  { key: 'converting', label: '1. 파일 변환' },
  { key: 'chunking', label: '2. 청킹' },
  { key: 'embedding', label: '3. 임베딩/저장' },
]

function stepStatus(stepKey, currentStep, failed) {
  const currentIndex = STEPS.findIndex((s) => s.key === currentStep)
  const stepIndex = STEPS.findIndex((s) => s.key === stepKey)
  if (currentStep === 'done' || stepIndex < currentIndex) return 'done'
  if (stepIndex === currentIndex) return failed ? 'failed' : 'active'
  return 'pending'
}

export default function ManualUploadProgressModal({ jobId, onDone, onClose }) {
  const [job, setJob] = useState({ step: 'converting', error_message: null })
  const doneNotifiedRef = useRef(false)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const data = await fetchUploadJobStatus(jobId)
        if (cancelled) return
        setJob(data)
      } catch {
        // 폴링 실패는 무시하고 다음 tick에 재시도
      }
    }

    poll()
    const interval = setInterval(poll, 1200)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [jobId])

  useEffect(() => {
    if (job.step === 'done' && !doneNotifiedRef.current) {
      doneNotifiedRef.current = true
      const timer = setTimeout(onDone, 600)
      return () => clearTimeout(timer)
    }
  }, [job.step, onDone])

  const failed = Boolean(job.error_message)

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h3 className="panel__title">매뉴얼 등록 진행 중</h3>
        <ul className="upload-steps">
          {STEPS.map((step) => {
            const status = stepStatus(step.key, job.step, failed)
            return (
              <li key={step.key} className={`upload-step upload-step--${status}`}>
                <span className="upload-step__icon">
                  {status === 'done' && '✓'}
                  {status === 'failed' && '✕'}
                </span>
                <span className="upload-step__label">{step.label}</span>
              </li>
            )
          })}
        </ul>
        {failed && (
          <>
            <div className="upload-error">오류: {job.error_message}</div>
            <button type="button" className="btn btn--primary" onClick={onClose}>닫기</button>
          </>
        )}
      </div>
    </div>
  )
}
