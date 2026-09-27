import { useCallback, useEffect, useRef, useState } from 'react'
import '@blocknote/core/fonts/inter.css'
import { BlockNoteEditor } from '@blocknote/core'
import { useCreateBlockNote } from '@blocknote/react'
import { BlockNoteView } from '@blocknote/mantine'
import '@blocknote/mantine/style.css'
import { deployManualDraft, fetchUploadJobStatus, getManualDraft, lockManual, saveManualDraft, unlockManual, verifyManual } from '../api'
import './EditorPanel.css'

const TAXONOMY_COLORS = {
  '여신': '#4a7fcb', '수신': '#4fad8a', '외환': '#8b72d4',
  '자금': '#d4843f', '카드': '#d45e6e', '고객': '#5b9fd4', '기타': '#8a9bb0',
}

const STEP_LABEL = {
  draft: '초안 편집 중',
  converting: '변환 중',
  chunking: '청킹 중',
  embedding: '임베딩 중',
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })
}

async function parseMarkdownToBlocks(markdown) {
  const editor = BlockNoteEditor.create()
  return editor.tryParseMarkdownToBlocks(markdown)
}

function BlockEditor({ initialContent, onChange, editable = true }) {
  const editor = useCreateBlockNote({
    initialContent: initialContent?.length > 0 ? initialContent : undefined,
  })
  return (
    <BlockNoteView
      editor={editor}
      theme="light"
      editable={editable}
      onChange={() => editable && onChange(editor.document)}
    />
  )
}

export default function EditorPanel({ manual, canEdit = false, onClose, isWide, onToggleWide, onOpenTerms, onLockChange }) {
  const currentUser = localStorage.getItem('manual_system_username') || ''
  const [blocks, setBlocks] = useState(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [saveStatus, setSaveStatus] = useState('saved')
  const [deployStatus, setDeployStatus] = useState('idle')
  const [deleting] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState(null)
  const [lockInfo, setLockInfo] = useState({ locked_by: manual?.locked_by || null, locked_at: manual?.locked_at || null })
  const [locking, setLocking] = useState(false)
  const saveTimer = useRef(null)
  const pollTimer = useRef(null)
  const pendingContent = useRef(null)
  const latestContent = useRef(null)
  const originalContent = useRef(null)

  const isLockedByMe = lockInfo.locked_by === currentUser
  const isLockedByOther = Boolean(lockInfo.locked_by && lockInfo.locked_by !== currentUser)
  const verifyPassed = Boolean(verifyResult && !verifyResult.error)
  const editable = canEdit && isLockedByMe

  useEffect(() => {
    if (!manual) return
    setBlocks(null)
    setHasChanges(false)
    setSaveStatus('saved')
    setDeployStatus('idle')
    setVerifyResult(null)
    pendingContent.current = null
    latestContent.current = null
    originalContent.current = null

    setLockInfo({ locked_by: manual?.locked_by || null, locked_at: manual?.locked_at || null })

    let cancelled = false
    getManualDraft(manual.id).then(async data => {
      if (cancelled) return
      let loadedBlocks
      if (data.from_chunks && data.raw_markdown) {
        loadedBlocks = await parseMarkdownToBlocks(data.raw_markdown)
      } else {
        loadedBlocks = data.content || []
      }
      if (!cancelled) {
        setBlocks(loadedBlocks)
        originalContent.current = loadedBlocks
      }
    }).catch(() => {
      if (!cancelled) setBlocks([])
    })

    return () => {
      cancelled = true
      if (saveTimer.current) clearTimeout(saveTimer.current)
      if (pollTimer.current) clearTimeout(pollTimer.current)
    }
  }, [manual?.id])

  const handleLock = async () => {
    setLocking(true)
    try {
      if (isLockedByMe) {
        const res = await unlockManual(manual.id)
        setLockInfo({ locked_by: res.locked_by, locked_at: null })
      } else {
        const res = await lockManual(manual.id)
        setLockInfo({ locked_by: res.locked_by, locked_at: new Date().toISOString() })
      }
      // 보드의 카드 잠금 배지는 부모가 들고 있는 manuals 목록을 보고 그리므로,
      // 여기서 로컬 lockInfo만 바꾸면 30초 폴링 전까지는 반영되지 않는다.
      onLockChange?.()
    } catch (e) {
      alert(e.message)
    } finally {
      setLocking(false)
    }
  }

  const handleChange = useCallback((newBlocks) => {
    if (!editable) return
    setHasChanges(true)
    setVerifyResult(null) // 수정하면 검증 무효화 → 운영반영 비활성화
    pendingContent.current = newBlocks
    latestContent.current = newBlocks
    setSaveStatus('unsaved')
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      try {
        await saveManualDraft(manual.id, newBlocks)
        pendingContent.current = null
        setSaveStatus('saved')
      } catch {
        setSaveStatus('error')
      }
    }, 1500)
  }, [manual?.id, editable])

  const handleSaveNow = async () => {
    const content = latestContent.current
    if (!content) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    setSaveStatus('saving')
    try {
      await saveManualDraft(manual.id, content)
      pendingContent.current = null
      setSaveStatus('saved')
    } catch {
      setSaveStatus('error')
    }
  }

  const handleDeploy = async () => {
    if (deployStatus === 'deploying') return
    if (pendingContent.current) {
      try { await saveManualDraft(manual.id, pendingContent.current) } catch {}
    }
    setDeployStatus('deploying')
    try {
      const { job_id } = await deployManualDraft(manual.id)
      const poll = async () => {
        try {
          const job = await fetchUploadJobStatus(job_id)
          if (job.step === 'done') {
            setDeployStatus('done')
          } else if (job.error_message) {
            setDeployStatus('error')
          } else {
            pollTimer.current = setTimeout(poll, 2500)
          }
        } catch {
          setDeployStatus('error')
        }
      }
      poll()
    } catch {
      setDeployStatus('error')
    }
  }

  const handleVerify = async () => {
    const content = latestContent.current ?? blocks
    if (!content) return
    if (pendingContent.current) {
      try { await saveManualDraft(manual.id, pendingContent.current) } catch {}
    }
    setVerifying(true)
    setVerifyResult(null)
    try {
      const result = await verifyManual(manual.id, content, originalContent.current)
      setVerifyResult(result)
    } catch (e) {
      setVerifyResult({ error: e.message || '검증에 실패했습니다.' })
    } finally {
      setVerifying(false)
    }
  }

  if (!manual) return null

  const cat = manual.categories?.[0]
  const catColor = TAXONOMY_COLORS[cat] || '#888'
  const doneVer = manual.latest_done_version_no
  const draftStep = manual.latest_draft_index_step

  return (
    <div className="ep-panel">
      {/* ── 왼쪽 확장 핸들 ── */}
      {onToggleWide && (
        <button className={`ep-expand-handle${isWide ? ' ep-expand-handle--wide' : ''}`} onClick={onToggleWide} title={isWide ? '패널 축소' : '패널 확장'}>
          {isWide ? '›' : '‹'}
        </button>
      )}

      {/* ── 헤더 ── */}
      <div className="ep-header">
        <div className="ep-breadcrumb">
          {cat && <span className="ep-breadcrumb__cat" style={{ color: catColor }}>{cat}</span>}
          {cat && <span className="ep-breadcrumb__sep">›</span>}
          <span className="ep-breadcrumb__title">{manual.title}</span>
        </div>
        {!canEdit ? (
          <span className="ep-lock-badge ep-lock-badge--other" title="이 카드는 소속 팀만 수정할 수 있습니다">
            👁 읽기 전용
          </span>
        ) : isLockedByOther ? (
          <span className="ep-lock-badge ep-lock-badge--other" title={`${lockInfo.locked_by}님이 편집 중`}>
            🔒 {lockInfo.locked_by}
          </span>
        ) : (
          <button
            className={`ep-lock-btn${isLockedByMe ? ' ep-lock-btn--locked' : ''}`}
            onClick={handleLock}
            disabled={locking}
            title={isLockedByMe ? '잠금 해제' : '편집 잠금'}
          >
            {locking ? '...' : isLockedByMe ? '🔒 잠금 해제' : '🔓 잠금'}
          </button>
        )}
        <button className="ep-close" onClick={onClose} title="닫기">✕</button>
      </div>

      {/* ── 메타 정보 ── */}
      <div className="ep-meta">
        <div className="ep-meta__info">
          <span className="ep-meta__item">
            <span className="ep-meta__label">작성자</span>
            <span className="ep-meta__value">{manual.created_by ?? '—'}</span>
          </span>
          <span className="ep-meta__dot">·</span>
          <span className="ep-meta__item">
            <span className="ep-meta__label">작성일</span>
            <span className="ep-meta__value">{formatDate(manual.created_at)}</span>
          </span>
          {manual.lang_c && (
            <>
              <span className="ep-meta__dot">·</span>
              <span className="ep-meta__item">
                <span className="ep-meta__label">언어</span>
                <span className="ep-meta__value">{manual.lang_c === 'ko' ? '한국어' : 'English'}</span>
              </span>
            </>
          )}
        </div>
        <div className="ep-meta__badges">
          {doneVer != null && (
            <span className="ep-meta__badge ep-meta__badge--done">v{doneVer} 서비스 중</span>
          )}
          {draftStep === 'draft' && (
            <span className="ep-meta__badge ep-meta__badge--draft">초안 편집 중</span>
          )}
          {draftStep && draftStep !== 'draft' && draftStep !== 'done' && (
            <span className="ep-meta__badge ep-meta__badge--indexing">
              {STEP_LABEL[draftStep] ?? draftStep}
            </span>
          )}
          {!doneVer && !draftStep && (
            <span className="ep-meta__badge ep-meta__badge--draft">새 매뉴얼</span>
          )}
        </div>
      </div>

      {/* ── 에디터 ── */}
      <div className="ep-editor-wrap">
        {blocks === null ? (
          <div className="ep-loading">매뉴얼을 불러오는 중...</div>
        ) : (
          <BlockEditor key={manual.id} initialContent={blocks} onChange={handleChange} editable={editable} />
        )}
      </div>

      {/* ── AI 검증 결과 ── */}
      {verifyResult && (
        <div className="ep-verify-result">
          {verifyResult.error ? (
            <div className="ep-verify-result__error">{verifyResult.error}</div>
          ) : (
            <>
              <div className="ep-verify-result__header">
                <span className="ep-verify-result__title">AI 검증 결과</span>
                <span className={`ep-verify-result__score ep-verify-result__score--${verifyResult.score >= 80 ? 'good' : verifyResult.score >= 60 ? 'mid' : 'bad'}`}>
                  {verifyResult.score}점
                </span>
                <button className="ep-verify-result__close" onClick={() => setVerifyResult(null)}>✕</button>
              </div>
              <p className="ep-verify-result__summary">{verifyResult.summary}</p>
              {verifyResult.added_review && (
                <div className="ep-verify-result__section">
                  <div className="ep-verify-result__section-label ep-verify-result__section-label--added">이번 편집 내용 검토</div>
                  <p className="ep-verify-result__added-text">{verifyResult.added_review}</p>
                </div>
              )}
              {verifyResult.unknown_terms?.length > 0 && (
                <div className="ep-verify-result__section">
                  <div className="ep-verify-result__section-label ep-verify-result__section-label--unknown">감지된 미등록 용어</div>
                  <div className="ep-verify-result__unknown-list">
                    {verifyResult.unknown_terms.map((t, i) => (
                      <div key={i} className="ep-verify-result__unknown-item">
                        <span className="ep-verify-result__unknown-term">{t.term}</span>
                        <span className="ep-verify-result__unknown-reason">{t.reason}</span>
                        {onOpenTerms && (
                          <button
                            className="ep-verify-result__unknown-reg"
                            onClick={() => onOpenTerms({ term: t.term, aliases: '' })}
                          >+ 등록</button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {verifyResult.issues?.length > 0 && (
                <div className="ep-verify-result__section">
                  <div className="ep-verify-result__section-label ep-verify-result__section-label--issues">문제점</div>
                  <ul className="ep-verify-result__list">
                    {verifyResult.issues.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}
              {verifyResult.suggestions?.length > 0 && (
                <div className="ep-verify-result__section">
                  <div className="ep-verify-result__section-label ep-verify-result__section-label--suggestions">개선 제안</div>
                  <ul className="ep-verify-result__list">
                    {verifyResult.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── 푸터 (저장 + 배포) ── */}
      <div className="ep-footer">
        {!canEdit ? (
          <span className="ep-save-status ep-save-status--locked">👁 이 카드는 소속 팀만 수정할 수 있습니다</span>
        ) : isLockedByOther ? (
          <span className="ep-save-status ep-save-status--locked">🔒 읽기 전용</span>
        ) : !isLockedByMe ? (
          <span className="ep-save-status ep-save-status--hint">잠금 후 편집할 수 있습니다</span>
        ) : (
          <span className={`ep-save-status ep-save-status--${saveStatus}`}>
            {saveStatus === 'unsaved' && '변경사항 있음'}
            {saveStatus === 'saving'  && '저장 중...'}
            {saveStatus === 'saved'   && (hasChanges ? '✓ 저장됨' : '변경사항 없음')}
            {saveStatus === 'error'   && '저장 실패'}
          </span>
        )}
        <div className="ep-footer__actions">
          {/* AI 검증: 잠금 + 변경사항 있을 때만 활성 */}
          <button
            className="ep-verify-btn"
            onClick={handleVerify}
            disabled={!editable || !hasChanges || verifying}
            title={!editable ? '편집 잠금 후 사용 가능' : !hasChanges ? '수정 내용이 없습니다' : undefined}
          >
            {verifying ? 'AI 검증 중...' : 'AI 검증'}
          </button>
          {/* 저장: 잠금 + 변경사항 있을 때만 활성 */}
          <button
            className={`ep-save-btn${saveStatus === 'saved' && hasChanges ? ' ep-save-btn--saved' : ''}`}
            onClick={handleSaveNow}
            disabled={!editable || !hasChanges || saveStatus === 'saving' || saveStatus === 'saved'}
          >
            {saveStatus === 'saving' ? '저장 중...' : saveStatus === 'saved' && hasChanges ? '저장됨' : '저장'}
          </button>
          {/* 운영반영: AI 검증 완료 후에만 활성 */}
          <button
            className={`ep-deploy-btn ep-deploy-btn--${deployStatus}`}
            onClick={handleDeploy}
            disabled={!editable || !verifyPassed || deployStatus === 'deploying' || deployStatus === 'done'}
            title={!editable ? '편집 잠금 후 사용 가능' : !verifyPassed ? 'AI 검증 완료 후 사용 가능' : undefined}
          >
            {deployStatus === 'idle'      && '운영반영'}
            {deployStatus === 'deploying' && '배포 중...'}
            {deployStatus === 'done'      && '✓ 배포완료'}
            {deployStatus === 'error'     && '재시도'}
          </button>
        </div>
      </div>
    </div>
  )
}
