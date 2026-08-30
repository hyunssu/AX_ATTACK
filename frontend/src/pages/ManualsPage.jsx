import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchManuals } from '../api'
import ManualItem from '../components/ManualItem'
import { SECTION_CATEGORIES } from '../constants'

export default function ManualsPage() {
  const [manuals, setManuals] = useState([])
  const [activeCategory, setActiveCategory] = useState('전체')
  const navigate = useNavigate()

  const loadManuals = useCallback(async () => {
    const list = await fetchManuals()
    setManuals(list)
  }, [])

  useEffect(() => {
    loadManuals()
  }, [loadManuals])

  const categories = useMemo(() => ['전체', ...SECTION_CATEGORIES], [])

  const filteredManuals = useMemo(
    () => (activeCategory === '전체' ? manuals : manuals.filter((m) => m.categories?.includes(activeCategory))),
    [manuals, activeCategory]
  )

  return (
    <main className="page-layout page-layout--wide">
      <section className="hero hero--split">
        <div>
          <div className="eyebrow">MANUAL SYSTEM</div>
          <h1 className="hero__title">필요한 순간, 정확한 매뉴얼을 찾다</h1>
          <p className="hero__subtitle">등록된 업무 매뉴얼을 살펴보고 최신 버전을 확인하세요</p>
        </div>
        <button type="button" className="btn btn--primary" onClick={() => navigate('/manuals/new')}>
          + 새 매뉴얼
        </button>
      </section>
      <nav className="category-tabs">
        {categories.map((category) => (
          <button
            key={category}
            type="button"
            className={`category-tab${activeCategory === category ? ' category-tab--active' : ''}`}
            onClick={() => setActiveCategory(category)}
          >
            {category}
          </button>
        ))}
      </nav>
      <section className="manual-grid">
        {filteredManuals.length === 0 && <p className="status-text">해당 분류의 매뉴얼이 없습니다.</p>}
        {filteredManuals.map((manual) => (
          <ManualItem
            key={manual.id}
            manual={manual}
            versionCount={manual.version_count}
            onSelect={() => navigate(`/manuals/${manual.id}`)}
          />
        ))}
      </section>
    </main>
  )
}
