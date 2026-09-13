import { useEffect, useState } from 'react'
import {
  addFaqMessage,
  approveFaq,
  deleteFaqMessage,
  getFaq,
  listFaqAssignees,
  listFaqs,
  reassignFaq,
  refineFaq,
  rejectFaq,
} from '../api'

const STATUS_LABELS = {
  pending: '답변 대기',
  assigned: '재배정',
  approved: '완료',
  rejected: '반려',
}

const STATUS_TABS = {
  ...STATUS_LABELS,
  all: '전체',
}

function formatCompactDateTime(dateValue, timeValue) {
  if (!dateValue || !timeValue) return '-'
  const date = String(dateValue).trim()
  const time = String(timeValue).trim()
  if (date.length !== 8 || time.length !== 6) return `${date} ${time}`
  return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)} ${time.slice(0, 2)}:${time.slice(2, 4)}:${time.slice(4, 6)}`
}

export default function FAQReviewPage() {
  const [status, setStatus] = useState('pending')
  const [queryInput, setQueryInput] = useState('')
  const [query, setQuery] = useState('')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [keywords, setKeywords] = useState('')
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState('answer')
  const [assignees, setAssignees] = useState([])
  const [assignee, setAssignee] = useState('')
  const [knowledgeSearchAllowed, setKnowledgeSearchAllowed] = useState(true)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function loadList() {
    setLoading(true)
    setError('')
    try {
      const data = await listFaqs(status, query)
      setItems(data.items)
      setTotal(data.total)
      if (selectedId && !data.items.some((item) => item.faq_id === selectedId)) {
        setSelectedId(null)
        setDetail(null)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let active = true
    listFaqs(status, query)
      .then((data) => {
        if (!active) return
        setItems(data.items)
        setTotal(data.total)
      })
      .catch((err) => {
        if (active) setError(err.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [status, query])

  useEffect(() => {
    listFaqAssignees().then(setAssignees).catch((err) => setError(err.message))
  }, [])

  async function selectFaq(faqId) {
    setSelectedId(faqId)
    setError('')
    try {
      const data = await getFaq(faqId)
      setDetail(data)
      setQuestion(data.summarized_question || data.refined_question || data.original_question)
      setAnswer(data.summarized_answer || '')
      setKeywords((data.final_keywords || []).join(', '))
      setAssignee(data.assignee_username || '')
      setKnowledgeSearchAllowed(data.knowledge_search_allowed !== 'N')
    } catch (err) {
      setError(err.message)
    }
  }

  async function reloadDetail() {
    if (!selectedId) return
    const data = await getFaq(selectedId)
    setDetail(data)
    setQuestion(data.summarized_question || data.refined_question || data.original_question)
    setAnswer(data.summarized_answer || '')
    setKeywords((data.final_keywords || []).join(', '))
    setAssignee(data.assignee_username || '')
    setKnowledgeSearchAllowed(data.knowledge_search_allowed !== 'N')
  }

  async function runAction(action) {
    if (!detail) return
    setSaving(true)
    setError('')
    try {
      if (action === 'message') {
        if (!message.trim()) throw new Error('메시지를 입력해 주세요.')
        await addFaqMessage(detail.faq_id, message.trim(), messageType)
        setMessage('')
        await reloadDetail()
      } else if (action === 'refine') {
        const data = await refineFaq(detail.faq_id)
        setQuestion(data.summarized_question || '')
        setAnswer(data.summarized_answer || '')
        setKeywords((data.final_keywords || []).join(', '))
        await reloadDetail()
      } else if (action === 'reassign') {
        await reassignFaq(detail.faq_id, assignee)
        await loadList()
        await reloadDetail()
      } else if (action === 'approve') {
        if (!question.trim() || !answer.trim()) throw new Error('최종 질문과 답변을 모두 입력해 주세요.')
        const completionMode = knowledgeSearchAllowed
          ? '완료하고 답변 검색 지식으로 등록할까요?'
          : '완료하되 답변 검색에는 사용하지 않을까요?'
        if (!window.confirm(`FAQ 요청 #${detail.faq_id}을 ${completionMode}`)) return
        await approveFaq(detail.faq_id, {
          question: question.trim(),
          answer: answer.trim(),
          keywords: keywords.split(',').map((item) => item.trim()).filter(Boolean),
          knowledge_search_allowed: knowledgeSearchAllowed,
        })
        setSelectedId(null)
        setDetail(null)
        await loadList()
      } else if (action === 'reject') {
        const reason = window.prompt('질문자에게 전달할 반려 사유를 입력해 주세요.')
        if (!reason?.trim()) return
        await rejectFaq(detail.faq_id, reason.trim())
        setSelectedId(null)
        setDetail(null)
        await loadList()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function removeMessage(item) {
    if (!detail || !editable) return
    if (!window.confirm('이 메시지를 삭제할까요? 원본 채팅방에 전달된 AI 메시지도 함께 삭제됩니다.')) return
    setSaving(true)
    setError('')
    try {
      await deleteFaqMessage(detail.faq_id, item.faq_chat_id)
      await reloadDetail()
      await loadList()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  function submitSearch(event) {
    event.preventDefault()
    setQuery(queryInput.trim())
  }

  const editable = detail && ['pending', 'assigned'].includes(detail.status)

  return (
    <main className="faq-review-page">
      <header className="faq-review-header">
        <div>
          <div className="eyebrow">FAQ REQUEST WORKSPACE</div>
          <h1>미해결 질문 검수</h1>
          <p>담당자와 질문자가 추가 확인한 뒤 최종 질문/답변만 승인 FAQ 지식으로 등록합니다.</p>
        </div>
        <form className="faq-search" onSubmit={submitSearch}>
          <input value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="질문 또는 담당자 검색" />
          <button type="submit" className="btn btn--primary">검색</button>
        </form>
      </header>

      <div className="faq-status-tabs">
        {Object.entries(STATUS_TABS).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={`faq-status-tab${status === value ? ' active' : ''}`}
            onClick={() => { setLoading(true); setStatus(value); setSelectedId(null); setDetail(null) }}
          >
            {label}
          </button>
        ))}
        <span className="faq-status-count">{total}건</span>
      </div>

      {error && <div className="faq-review-error">{error}</div>}

      <div className="faq-review-layout">
        <section className="faq-list-panel">
          {loading && <div className="faq-empty">목록을 불러오는 중입니다.</div>}
          {!loading && items.length === 0 && <div className="faq-empty">해당 상태의 요청이 없습니다.</div>}
          {items.map((item) => (
            <button
              key={item.faq_id}
              type="button"
              className={`faq-list-item${selectedId === item.faq_id ? ' active' : ''}`}
              onClick={() => selectFaq(item.faq_id)}
            >
              <span className="faq-list-item__meta">
                요청 #{item.faq_id} · {item.assignee_display_name || item.assignee_username}
                <span className={`faq-status-badge faq-status-badge--${item.status}`}>{STATUS_LABELS[item.status]}</span>
              </span>
              <strong>{item.refined_question}</strong>
              <span>{formatCompactDateTime(item.last_change_date, item.last_change_time)}</span>
            </button>
          ))}
        </section>

        <section className="faq-editor-panel">
          {!detail && <div className="faq-empty">왼쪽에서 처리할 요청을 선택하세요.</div>}
          {detail && (
            <>
              <div className="faq-editor-meta">
                <span className={`faq-status-badge faq-status-badge--${detail.status}`}>{STATUS_LABELS[detail.status]}</span>
                <span>요청 #{detail.faq_id}</span>
                <span>등록 {formatCompactDateTime(detail.regis_date, detail.regis_time)}</span>
                <span>요청자 {detail.requester_username}</span>
              </div>

              <div className="faq-request-facts">
                <span><strong>대상업무</strong>{detail.target_business || '미확인'}</span>
                <span><strong>화면번호</strong>{detail.screen_number || '미확인'}</span>
                <span><strong>국가</strong>{detail.country || '미확인'}</span>
                <span><strong>배정 근거</strong>{detail.assignment_reason || '-'}</span>
                <span><strong>신뢰도</strong>{detail.assignment_confidence || '-'}</span>
              </div>

              <div className="faq-reassign-row">
                <label>
                  담당자
                  <select value={assignee} onChange={(event) => setAssignee(event.target.value)} disabled={!editable}>
                    {assignees.map((item) => (
                      <option key={item.username} value={item.username}>
                        {item.display_name} ({item.username}) · {item.department || '소속 미등록'}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="button" className="btn btn--ghost" disabled={!editable || saving} onClick={() => runAction('reassign')}>
                  재배정
                </button>
              </div>

              <div className="faq-source-conversation faq-request-chat">
                <h2>질문자·담당자 대화</h2>
                {detail.messages.map((item) => (
                  <div key={item.faq_chat_id} className={`faq-source-message faq-source-message--${item.author_role}`}>
                    {editable && ['answer', 'additional_question', 'note'].includes(item.message_type) && (
                      <button
                        type="button"
                        className="faq-message-delete"
                        title="메시지 삭제"
                        aria-label="메시지 삭제"
                        disabled={saving}
                        onClick={() => removeMessage(item)}
                      >
                        🗑
                      </button>
                    )}
                    <span>{item.author_username} · {item.message_type} · {formatCompactDateTime(item.regis_date, item.regis_time)}</span>
                    <p>{item.message_text}</p>
                  </div>
                ))}
                {editable && (
                  <div className="faq-message-compose">
                    <select
                      aria-label="메시지 유형"
                      value={messageType}
                      onChange={(event) => setMessageType(event.target.value)}
                    >
                      <option value="answer">답변 작성</option>
                      <option value="additional_question">질문자에게 추가질의</option>
                      <option value="note">내부 메모</option>
                    </select>
                    <textarea
                      rows="4"
                      value={message}
                      onChange={(event) => setMessage(event.target.value)}
                      placeholder="담당자 메시지를 입력하세요."
                    />
                    <button type="button" className="btn btn--primary" disabled={saving} onClick={() => runAction('message')}>
                      등록
                    </button>
                  </div>
                )}
              </div>

              <div className="faq-final-header">
                <h2>최종 FAQ 질문/답변</h2>
                {editable && <button type="button" className="btn btn--ghost" disabled={saving} onClick={() => runAction('refine')}>자동요약</button>}
              </div>
              <label className="faq-field">
                <span>질문</span>
                <textarea rows="3" value={question} disabled={!editable} onChange={(event) => setQuestion(event.target.value)} />
              </label>
              <label className="faq-field">
                <span>답변</span>
                <textarea rows="7" value={answer} disabled={!editable} onChange={(event) => setAnswer(event.target.value)} />
              </label>
              <label className="faq-field">
                <span>키워드 <small>쉼표로 구분</small></span>
                <input value={keywords} disabled={!editable} onChange={(event) => setKeywords(event.target.value)} />
              </label>

              {detail.rejection_reason && <p className="faq-review-note">반려 사유: {detail.rejection_reason}</p>}
              {(editable || detail.status === 'approved') && (
                <div className="faq-completion-controls">
                  <label className="faq-knowledge-toggle">
                    <input
                      type="checkbox"
                      checked={knowledgeSearchAllowed}
                      disabled={!editable || saving}
                      onChange={(event) => setKnowledgeSearchAllowed(event.target.checked)}
                    />
                    <span>
                      지식검색 허용
                      <small>{knowledgeSearchAllowed ? '완료 후 답변 검색에 사용' : 'FAQ 완료 목록에서만 조회'}</small>
                    </span>
                  </label>
                  {editable && (
                    <div className="faq-editor-actions">
                      <button type="button" className="btn faq-btn--reject" disabled={saving} onClick={() => runAction('reject')}>반려</button>
                      <button
                        type="button"
                        className="btn btn--primary"
                        disabled={saving || !question.trim() || !answer.trim()}
                        onClick={() => runAction('approve')}
                      >
                        답변 완료 및 승인
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  )
}
