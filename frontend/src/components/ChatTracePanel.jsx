export default function ChatTracePanel({ trace }) {
  return (
    <div className="chat-trace-panel">
      {trace.steps.map((step, idx) => (
        <div key={idx} className="chat-trace-step">
          <div className="chat-trace-step__label">{step.label}</div>
          <div className="chat-trace-step__detail">{step.detail}</div>
          {step.chunks && (
            <div className="chat-trace-chunks">
              {step.chunks.map((chunk, cIdx) => (
                <div key={cIdx} className="chat-trace-chunk">
                  <div className="chat-trace-chunk__head">
                    <span className="chat-trace-chunk__title">{chunk.section_title}</span>
                    <span className="chat-trace-chunk__meta">
                      벡터 {chunk.vector_score} · 키워드 {chunk.keyword_score}
                    </span>
                  </div>
                  <p className="chat-trace-chunk__excerpt">{chunk.excerpt}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
