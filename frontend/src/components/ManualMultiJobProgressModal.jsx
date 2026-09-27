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

export default function ManualMultiJobProgressModal({ jobs, onDone, onClose }) {
  const [statuses, setStatuses] = useState(() =>
    Object.fromEntries(jobs.map((job) => [job.job_id, { step: 'converting', error_message: null }]))
  )
  const doneNotifiedRef = useRef(false)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      const entries = await Promise.all(
        jobs.map(async (job) => {
          try {
            const data = await fetchUploadJobStatus(job.job_id)
            return [job.job_id, data]
          } catch {
            return null
          }
        })
      )
      if (cancelled) return
      setStatuses((prev) => {
        const next = { ...prev }
        for (const entry of entries) {
          if (entry) next[entry[0]] = entry[1]
        }
        return next
      })
    }

    poll()
    const interval = setInterval(poll, 1200)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [jobs])

  const allDone = jobs.every((job) => statuses[job.job_id]?.step === 'done')

  useEffect(() => {
    if (allDone && !doneNotifiedRef.current) {
      doneNotifiedRef.current = true
      const timer = setTimeout(onDone, 600)
      return () => clearTimeout(timer)
    }
  }, [allDone, onDone])

  return (
    <div className="modal-overlay">
      <div className="modal-card modal-card--wide">
        <h3 className="panel__title">매뉴얼 등록 진행 중 ({jobs.length}건)</h3>
        <ul className="multi-job-progress">
          {jobs.map((job) => {
            const status = statuses[job.job_id] || { step: 'converting', error_message: null }
            const failed = Boolean(status.error_message)
            return (
              <li key={job.job_id} className="multi-job-progress__item">
                <div className="multi-job-progress__title">{job.title}</div>
                <ul className="upload-steps upload-steps--compact">
                  {STEPS.map((step) => {
                    const s = stepStatus(step.key, status.step, failed)
                    return (
                      <li key={step.key} className={`upload-step upload-step--${s}`}>
                        <span className="upload-step__icon">
                          {s === 'done' && '✓'}
                          {s === 'failed' && '✕'}
                        </span>
                        <span className="upload-step__label">{step.label}</span>
                      </li>
                    )
                  })}
                </ul>
                {failed && <div className="upload-error">오류: {status.error_message}</div>}
              </li>
            )
          })}
        </ul>
        <button type="button" className="btn btn--ghost" onClick={onClose}>닫기</button>
      </div>
    </div>
  )
}
