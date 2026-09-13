import { useCallback, useEffect, useRef, useState } from 'react'
import '@blocknote/core/fonts/inter.css'
import { BlockNoteEditor } from '@blocknote/core'
import { useCreateBlockNote } from '@blocknote/react'
import { BlockNoteView } from '@blocknote/mantine'
import '@blocknote/mantine/style.css'
import { deployManualDraft, fetchUploadJobStatus, getManualDraft, saveManualDraft } from '../api'
import './EditorPanel.css'

const TAXONOMY_COLORS = {
  '여신': '#4a7fcb', '수신': '#4fad8a', '외환': '#8b72d4',
  '자금': '#d4843f', '카드': '#d45e6e', '고객': '#5b9fd4', '기타': '#8a9bb0',
}

// 마크다운 → BlockNote 블록 변환 (헤드리스 에디터 사용)
async function parseMarkdownToBlocks(markdown) {
  const editor = BlockNoteEditor.create()
  return editor.tryParseMarkdownToBlocks(markdown)
}

// BlockEditor: initialContent가 확정된 뒤에만 렌더링
function BlockEditor({ initialContent, onChange }) {
  const editor = useCreateBlockNote({
    initialContent: initialContent?.length > 0 ? initialContent : undefined,
  })
  return (
    <BlockNoteView
      editor={editor}
      theme="light"
      onChange={() => onChange(editor.document)}
    />
  )
}

export default function EditorPanel({ manual, onClose }) {
  const [blocks, setBlocks] = useState(null)  // null = 로딩 중
  const [saveStatus, setSaveStatus] = useState('saved')
  const [deployStatus, setDeployStatus] = useState('idle')
  const saveTimer = useRef(null)
  const pollTimer = useRef(null)
  const pendingContent = useRef(null)

  useEffect(() => {
    if (!manual) return
    setBlocks(null)
    setSaveStatus('saved')
    setDeployStatus('idle')
    pendingContent.current = null

    let cancelled = false
    getManualDraft(manual.id).then(async data => {
      if (cancelled) return
      if (data.from_chunks && data.raw_markdown) {
        // 마크다운 → BlockNote 블록으로 변환
        const parsed = await parseMarkdownToBlocks(data.raw_markdown)
        if (!cancelled) setBlocks(parsed)
      } else {
        setBlocks(data.content || [])
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

  const handleChange = useCallback((newBlocks) => {
    pendingContent.current = newBlocks
    setSaveStatus('saving')
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      try {
        await saveManualDraft(manual.id, newBlocks)
        setSaveStatus('saved')
      } catch {
        setSaveStatus('error')
      }
    }, 1500)
  }, [manual?.id])

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

  if (!manual) return null

  const cat = manual.categories?.[0]
  const catColor = TAXONOMY_COLORS[cat] || '#888'

  return (
    <div className="ep-panel">
      <div className="ep-header">
        <div className="ep-breadcrumb">
          {cat && <span className="ep-breadcrumb__cat" style={{ color: catColor }}>{cat}</span>}
          {cat && <span className="ep-breadcrumb__sep">›</span>}
          <span className="ep-breadcrumb__title">{manual.title}</span>
        </div>
        <button className="ep-close" onClick={onClose} title="닫기">✕</button>
      </div>

      <div className="ep-editor-wrap">
        {blocks === null ? (
          <div className="ep-loading">매뉴얼을 불러오는 중...</div>
        ) : (
          <BlockEditor
            key={manual.id}
            initialContent={blocks}
            onChange={handleChange}
          />
        )}
      </div>

      <div className="ep-footer">
        <span className={`ep-save-status ep-save-status--${saveStatus}`}>
          {saveStatus === 'saving' && '저장 중...'}
          {saveStatus === 'saved' && '✓ 저장됨'}
          {saveStatus === 'error' && '저장 실패'}
        </span>
        <button
          className={`ep-deploy-btn ep-deploy-btn--${deployStatus}`}
          onClick={handleDeploy}
          disabled={deployStatus === 'deploying'}
        >
          {deployStatus === 'idle' && '운영반영'}
          {deployStatus === 'deploying' && '배포 중...'}
          {deployStatus === 'done' && '✓ 배포 완료'}
          {deployStatus === 'error' && '재시도'}
        </button>
      </div>
    </div>
  )
}
