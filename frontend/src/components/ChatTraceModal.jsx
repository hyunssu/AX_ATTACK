const ENGINE_LABELS = {
  langchain: 'LangChain',
  langgraph: 'LangGraph',
  faq: '승인 FAQ',
  database: '업무 원장',
  knowledge_router: 'FAQ·매뉴얼 비교',
  business_scope_redirect: '업무 범위 분기',
  chat_pipeline: '채팅 처리 파이프라인',
}

function normalizeTrace(trace) {
  if (typeof trace !== 'string') return trace || {}
  try {
    return JSON.parse(trace)
  } catch {
    return { engine: 'chat_pipeline', steps: [] }
  }
}

export default function ChatTracePopover({ trace, id }) {
  const normalized = normalizeTrace(trace)
  const steps = Array.isArray(normalized.steps) ? normalized.steps : []
  const engineLabel = ENGINE_LABELS[normalized.engine] || normalized.engine || '처리 기록'

  return (
    <div className="chat-trace-popover" id={id} role="tooltip">
      <div className="chat-trace-popover__header">
        답변 처리 이력 <span>{engineLabel}</span>
      </div>
      {steps.length === 0 ? (
        <div className="chat-trace-popover__empty">기록된 상세 단계가 없습니다.</div>
      ) : steps.map((step, index) => (
        <section className="chat-trace-popover__step" key={`${step.node || 'step'}-${index}`}>
          <div className="chat-trace-popover__step-title">
            <strong>{index + 1}. {step.label || step.node || '처리 단계'}</strong>
            {step.node && <code>{step.node}</code>}
          </div>
          <div className="chat-trace-popover__io">
            <span>INPUT</span>
            <pre>{JSON.stringify(step.input ?? null, null, 2)}</pre>
            <span>OUTPUT</span>
            <pre>{JSON.stringify(step.output ?? null, null, 2)}</pre>
          </div>
        </section>
      ))}
    </div>
  )
}
