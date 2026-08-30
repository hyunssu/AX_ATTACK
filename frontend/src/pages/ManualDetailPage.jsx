import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchManuals } from '../api'
import ManualDetailPanel from '../components/ManualDetailPanel'

export default function ManualDetailPage() {
  const { id } = useParams()
  const [manual, setManual] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadManual = useCallback(async () => {
    const list = await fetchManuals()
    setManual(list.find((m) => m.id === Number(id)) || null)
    setLoading(false)
  }, [id])

  useEffect(() => {
    loadManual()
  }, [loadManual])

  return (
    <main className="page-layout page-layout--wide">
      <Link to="/manuals" className="back-link">← 목록으로</Link>
      {loading && <p className="status-text">불러오는 중...</p>}
      {!loading && !manual && <p className="status-text">매뉴얼을 찾을 수 없습니다.</p>}
      {!loading && manual && <ManualDetailPanel manual={manual} onVersionAdded={loadManual} />}
    </main>
  )
}
