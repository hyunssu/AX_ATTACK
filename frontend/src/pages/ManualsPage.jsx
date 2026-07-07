import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchManuals } from '../api'
import ManualItem from '../components/ManualItem'

export default function ManualsPage() {
  const [manuals, setManuals] = useState([])
  const navigate = useNavigate()

  const loadManuals = useCallback(async () => {
    const list = await fetchManuals()
    setManuals(list)
  }, [])

  useEffect(() => {
    loadManuals()
  }, [loadManuals])

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
      <section className="manual-grid">
        {manuals.length === 0 && <p className="status-text">등록된 매뉴얼이 없습니다.</p>}
        {manuals.map((manual) => (
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
