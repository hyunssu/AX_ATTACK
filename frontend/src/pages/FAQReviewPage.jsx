import { useEffect, useState } from 'react'
import { approveFaq, getFaq, listFaqs, rejectFaq } from '../api'

const STATUS_LABELS = {
  pending: '검수 대기',
  approved: '승인',
  rejected: '반려',
}

const TYPE_LABELS = {
  conversation: '대화 요약',
  manual: '매뉴얼',
  screen_owner_change: '담당자 변경',
}

function formatDate(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  }).format(new Date(value))
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
      if (selectedId && !data.items.some((item) => item.id === selectedId)) {
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

  async function selectFaq(faqId) {
    setSelectedId(faqId)
    setError('')
    try {
      const data = await getFaq(faqId)
      setDetail(data)
      setQuestion(data.question)
      setAnswer(data.answer)
      setKeywords((data.keywords || []).join(', '))
    } catch (err) {
      setError(err.message)
    }
  }

  async function changeStatus(nextStatus) {
    if (!detail) return
    if (nextStatus === 'approved' && (!question.trim() || !answer.trim())) {
      setError('승인할 질문과 답변을 모두 입력해 주세요.')
      return
    }
    const action = nextStatus === 'approved' ? '승인' : '반려'
    if (!window.confirm(`FAQ #${detail.id}을(를) ${action}할까요?`)) return
    setSaving(true)
    setError('')
    try {
      if (nextStatus === 'approved') {
        await approveFaq(detail.id, {
          question: question.trim(),
          answer: answer.trim(),
          keywords: keywords.split(',').map((keyword) => keyword.trim()).filter(Boolean),
        })
      }
      else await rejectFaq(detail.id)
      setSelectedId(null)
      setDetail(null)
      await loadList()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  function submitSearch(event) {
    event.preventDefault()
    setLoading(true)
    setQuery(queryInput.trim())
  }

  return (
    <main className="faq-review-page">
      <header className="faq-review-header">
        <div>
          <div className="eyebrow">FAQ REVIEW</div>
          <h1>FAQ 검수</h1>
          <p>대화에서 생성된 FAQ를 수정하고 승인한 뒤 챗봇 검색에 반영합니다.</p>
        </div>
        <form className="faq-search" onSubmit={submitSearch}>
          <input value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="질문 또는 답변 검색" />
          <button type="submit" className="btn btn--primary">검색</button>
        </form>
      </header>

      <div className="faq-status-tabs">
        {Object.entries(STATUS_LABELS).map(([value, label]) => (
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
          {!loading && items.length === 0 && <div className="faq-empty">해당 상태의 FAQ가 없습니다.</div>}
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`faq-list-item${selectedId === item.id ? ' active' : ''}`}
              onClick={() => selectFaq(item.id)}
            >
              <span className="faq-list-item__meta">#{item.id} · {TYPE_LABELS[item.faq_type] || item.faq_type}</span>
              <strong>{item.question}</strong>
              <span>{formatDate(item.created_at)}</span>
            </button>
          ))}
        </section>

        <section className="faq-editor-panel">
          {!detail && <div className="faq-empty">왼쪽에서 검수할 FAQ를 선택하세요.</div>}
          {detail && (
            <>
              <div className="faq-editor-meta">
                <span className={`faq-status-badge faq-status-badge--${detail.status}`}>{STATUS_LABELS[detail.status]}</span>
                <span>FAQ #{detail.id}</span>
                <span>생성일 {formatDate(detail.created_at)}</span>
                {detail.approved_at && <span>승인일 {formatDate(detail.approved_at)}</span>}
              </div>

              <label className="faq-field">
                <span>질문</span>
                <textarea rows="3" value={question} onChange={(event) => setQuestion(event.target.value)} />
              </label>
              <label className="faq-field">
                <span>답변</span>
                <textarea rows="7" value={answer} onChange={(event) => setAnswer(event.target.value)} />
              </label>
              <label className="faq-field">
                <span>키워드 <small>쉼표로 구분</small></span>
                <input value={keywords} onChange={(event) => setKeywords(event.target.value)} />
              </label>

              <div className="faq-editor-actions">
                <button type="button" className="btn faq-btn--reject" disabled={saving} onClick={() => changeStatus('rejected')}>반려</button>
                <button type="button" className="btn btn--primary" disabled={saving} onClick={() => changeStatus('approved')}>
                  {detail.faq_type === 'screen_owner_change' ? '변경 이력 승인' : '승인 및 검색 반영'}
                </button>
              </div>

              {detail.faq_type === 'screen_owner_change' && (
                <p className="faq-review-note">담당자 변경 FAQ는 감사 이력으로만 관리되며 현재 담당자 답변 검색에는 사용되지 않습니다.</p>
              )}

              <div className="faq-source-conversation">
                <h2>원본 대화</h2>
                {detail.source_messages.length === 0 && <p>연결된 원본 대화가 없습니다.</p>}
                {detail.source_messages.map((message) => (
                  <div key={message.id} className={`faq-source-message faq-source-message--${message.role}`}>
                    <span>{message.role === 'user' ? '사용자' : 'AI'} · {formatDate(message.created_at)}</span>
                    <p>{message.text}</p>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  )
}
