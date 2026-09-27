import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchManuals, fetchCategories, fetchFavorites, addFavorite, removeFavorite } from '../api'
import ManualItem from '../components/ManualItem'

export default function ManualsPage() {
  const [manuals, setManuals] = useState([])
  const [activeCategory, setActiveCategory] = useState('전체')
  const [catNames, setCatNames] = useState(['여신', '수신', '외환', '자금', '카드', '고객', '기타'])
  const [viewMode, setViewMode] = useState('all') // 'all' | 'favorites'
  const [favoriteIds, setFavoriteIds] = useState(new Set())
  const navigate = useNavigate()

  const loadManuals = useCallback(async () => {
    const list = await fetchManuals()
    setManuals(list)
  }, [])

  useEffect(() => {
    loadManuals()
    fetchCategories()
      .then(data => { if (Array.isArray(data) && data.length > 0) setCatNames(data.map(c => c.name)) })
      .catch(() => {})
    fetchFavorites()
      .then(ids => { if (Array.isArray(ids)) setFavoriteIds(new Set(ids)) })
      .catch(() => {})
  }, [loadManuals])

  const handleToggleFavorite = useCallback(async (manualId) => {
    const isFav = favoriteIds.has(manualId)
    setFavoriteIds(prev => {
      const next = new Set(prev)
      isFav ? next.delete(manualId) : next.add(manualId)
      return next
    })
    try {
      isFav ? await removeFavorite(manualId) : await addFavorite(manualId)
    } catch {
      setFavoriteIds(prev => {
        const next = new Set(prev)
        isFav ? next.add(manualId) : next.delete(manualId)
        return next
      })
    }
  }, [favoriteIds])

  const categories = useMemo(() => ['전체', ...catNames], [catNames])

  const baseManuals = viewMode === 'favorites'
    ? manuals.filter(m => favoriteIds.has(m.id))
    : manuals

  const filteredManuals = useMemo(
    () => (activeCategory === '전체' ? baseManuals : baseManuals.filter((m) => m.categories?.includes(activeCategory))),
    [baseManuals, activeCategory]
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

      <div className="view-mode-tabs">
        <button
          type="button"
          className={`view-mode-tab${viewMode === 'all' ? ' view-mode-tab--active' : ''}`}
          onClick={() => setViewMode('all')}
        >
          전체
        </button>
        <button
          type="button"
          className={`view-mode-tab${viewMode === 'favorites' ? ' view-mode-tab--active' : ''}`}
          onClick={() => setViewMode('favorites')}
        >
          ★ 즐겨찾기 {favoriteIds.size > 0 && <span className="view-mode-tab__count">{favoriteIds.size}</span>}
        </button>
      </div>

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
        {filteredManuals.length === 0 && (
          <p className="status-text">
            {viewMode === 'favorites' ? '즐겨찾기한 매뉴얼이 없습니다.' : '해당 분류의 매뉴얼이 없습니다.'}
          </p>
        )}
        {filteredManuals.map((manual) => (
          <ManualItem
            key={manual.id}
            manual={manual}
            isFavorited={favoriteIds.has(manual.id)}
            onToggleFavorite={() => handleToggleFavorite(manual.id)}
            onSelect={() => navigate(`/manuals/${manual.id}`)}
          />
        ))}
      </section>
    </main>
  )
}
