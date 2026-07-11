import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { reclassifySection } from '../api'
import { SECTION_CATEGORIES } from '../constants'

export default function ManualSectionReviewList({ sections, onChange }) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [reclassifying, setReclassifying] = useState(false)
  const [reclassifyError, setReclassifyError] = useState('')

  if (sections.length === 0) {
    return <div className="section-preview--empty">문서에서 내용을 찾을 수 없습니다.</div>
  }

  const activeIndex = Math.min(selectedIndex, sections.length - 1)
  const active = sections[activeIndex]
  const needsReviewCount = sections.filter((s) => s.needs_review).length

  function updateSection(idx, patch) {
    onChange(sections.map((section, i) => (i === idx ? { ...section, ...patch } : section)))
  }

  async function handleReclassify(idx) {
    const section = sections[idx]
    setReclassifying(true)
    setReclassifyError('')
    try {
      const result = await reclassifySection(section.title, section.content)
      updateSection(idx, { category: result.category, needs_review: result.needs_review })
    } catch (err) {
      setReclassifyError(`오류: ${err.message}`)
    } finally {
      setReclassifying(false)
    }
  }

  return (
    <div className="section-review">
      <div className="section-review__summary">
        {sections.length}개 섹션으로 나뉘었습니다. 왼쪽에서 섹션을 선택해 확인하고 필요하면 수정하세요.
        {needsReviewCount > 0 && (
          <span className="section-review__summary-flag"> 분류 확인이 필요한 섹션이 {needsReviewCount}개 있어요.</span>
        )}
      </div>
      <div className="section-review__split">
        <ul className="section-review-nav">
          {sections.map((section, idx) => (
            <li key={idx}>
              <button
                type="button"
                className={`section-review-nav__item${idx === activeIndex ? ' section-review-nav__item--active' : ''}${section.include ? '' : ' section-review-nav__item--excluded'}`}
                onClick={() => setSelectedIndex(idx)}
              >
                <input
                  type="checkbox"
                  checked={section.include}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => updateSection(idx, { include: e.target.checked })}
                />
                <span className="section-review-nav__title">{section.title || '(제목 없음)'}</span>
                {section.needs_review && <span className="section-review-nav__flag" title="분류 확인 필요">⚠</span>}
                <span className="section-review-nav__category">{section.category}</span>
              </button>
            </li>
          ))}
        </ul>
        <div className="section-review-detail">
          {active.needs_review && (
            <div className="section-review-detail__flag">
              <span>⚠ 분류 확신도가 낮아요. 내용을 확인하고 분류가 맞는지 점검해 주세요.</span>
              <button
                type="button"
                className="btn btn--ghost section-review-detail__reclassify"
                onClick={() => handleReclassify(activeIndex)}
                disabled={reclassifying}
              >
                {reclassifying ? '재분류 중…' : '정밀 재분류 요청'}
              </button>
            </div>
          )}
          {reclassifyError && <div className="status-text">{reclassifyError}</div>}
          <div className="form-field">
            <label htmlFor="section-review-title">매뉴얼 제목</label>
            <input
              id="section-review-title"
              type="text"
              value={active.title}
              onChange={(e) => updateSection(activeIndex, { title: e.target.value })}
            />
          </div>
          <div className="section-review-detail__row">
            <div className="form-field">
              <label htmlFor="section-review-category">분류</label>
              <select
                id="section-review-category"
                value={active.category}
                onChange={(e) => updateSection(activeIndex, { category: e.target.value })}
              >
                {SECTION_CATEGORIES.map((category) => (
                  <option key={category} value={category}>{category}</option>
                ))}
              </select>
            </div>
            <label className="section-review__include">
              <input
                type="checkbox"
                checked={active.include}
                onChange={(e) => updateSection(activeIndex, { include: e.target.checked })}
              />
              이 섹션 포함
            </label>
            <span className="section-preview__meta">{active.char_count.toLocaleString()}자</span>
          </div>
          <div className="section-review-detail__content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{active.content}</ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  )
}
