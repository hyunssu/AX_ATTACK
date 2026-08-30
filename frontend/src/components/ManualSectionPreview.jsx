export default function ManualSectionPreview({ sections }) {
  if (sections.length === 0) {
    return <div className="section-preview section-preview--empty">문서에서 내용을 찾을 수 없습니다.</div>
  }

  return (
    <div className="section-preview">
      <div className="section-preview__summary">{sections.length}개 섹션으로 나뉘었습니다</div>
      <ol className="section-preview__list">
        {sections.map((section, idx) => (
          <li key={idx} className="section-preview__item">
            <div className="section-preview__item-head">
              <span className="section-preview__title">{section.title || '(제목 없음)'}</span>
              <span className="section-preview__meta">{section.char_count.toLocaleString()}자</span>
            </div>
            <p className="section-preview__excerpt">
              {section.content.slice(0, 120)}
              {section.content.length > 120 ? '…' : ''}
            </p>
          </li>
        ))}
      </ol>
    </div>
  )
}
