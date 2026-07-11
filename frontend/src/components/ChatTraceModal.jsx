import { useState } from 'react'

function CollapsibleBlock({ label, value }) {
  const [open, setOpen] = useState(true)

  return (
    <div className="trace-step__block">
      <button
        type="button"
        className="trace-step__block-label trace-step__block-toggle"
        onClick={() => setOpen(!open)}
      >
        <span className="trace-step__caret">{open ? '▼' : '▶'}</span> {label}
      </button>
      {open && <pre className="trace-step__json">{JSON.stringify(value, null, 2)}</pre>}
    </div>
  )
}

function StepJsonBlocks({ step }) {
  return (
    <>
      <CollapsibleBlock label="input" value={step.input} />
      <CollapsibleBlock label="output" value={step.output} />
    </>
  )
}

function FlowSteps({ steps }) {
  const [selected, setSelected] = useState(0)
  const step = steps[selected]

  return (
    <div className="trace-modal__body">
      <div className="trace-flow__viewport">
        <div className="trace-flow">
          {steps.map((s, idx) => (
            <div key={idx} className={`trace-flow__node${idx === selected ? ' trace-flow__node--active' : ''}`}>
              <button type="button" className="trace-flow__circle-btn" onClick={() => setSelected(idx)}>
                <span className="trace-flow__circle">{idx + 1}</span>
              </button>
              <span className="trace-flow__label">{s.label}</span>
            </div>
          ))}
        </div>
      </div>
      {step && (
        <div className="trace-step__content trace-flow__detail">
          <div className="trace-step__node">{step.node}</div>
          <StepJsonBlocks step={step} />
        </div>
      )}
    </div>
  )
}

const ENGINE_LABELS = {
  langchain: 'LangChain',
}

export default function ChatTraceModal({ trace, onClose }) {
  const engineLabel = ENGINE_LABELS[trace.engine]

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card trace-modal" onClick={(e) => e.stopPropagation()}>
        <div className="trace-modal__header">
          <h3 className="panel__title">답변 과정{engineLabel ? ` (${engineLabel})` : ''}</h3>
          <button type="button" className="btn btn--ghost trace-modal__close" onClick={onClose}>닫기</button>
        </div>
        <FlowSteps steps={trace.steps} />
      </div>
    </div>
  )
}
