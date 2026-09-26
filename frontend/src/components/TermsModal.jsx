import { useEffect, useState } from 'react'
import { fetchTerms, createTerm, deleteTerm } from '../api'
import './TermsModal.css'

export default function TermsModal({ onClose, initialTerm }) {
  const [terms, setTerms] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ term: initialTerm?.term || '', aliases: initialTerm?.aliases || '', description: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchTerms().then(data => { setTerms(data); setLoading(false) })
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.term.trim() || !form.description.trim()) return
    setSaving(true)
    setError(null)
    try {
      const aliases = form.aliases.split(',').map(a => a.trim()).filter(Boolean)
      const created = await createTerm(form.term.trim(), aliases, form.description.trim())
      setTerms(prev => {
        const idx = prev.findIndex(t => t.id === created.id)
        return idx >= 0 ? prev.map(t => t.id === created.id ? created : t) : [created, ...prev]
      })
      setForm({ term: '', aliases: '', description: '' })
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('이 용어를 삭제할까요?')) return
    await deleteTerm(id)
    setTerms(prev => prev.filter(t => t.id !== id))
  }

  return (
    <div className="terms-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="terms-modal">
        <div className="terms-modal__header">
          <span className="terms-modal__title">용어 사전</span>
          <button className="terms-modal__close" onClick={onClose}>✕</button>
        </div>

        {/* 추가 폼 */}
        <form className="terms-form" onSubmit={handleSubmit}>
          <div className="terms-form__row">
            <input
              className="terms-form__input terms-form__input--term"
              placeholder="용어 (예: SWING)"
              value={form.term}
              onChange={e => setForm(f => ({ ...f, term: e.target.value }))}
            />
            <input
              className="terms-form__input terms-form__input--aliases"
              placeholder="별칭 (쉼표 구분, 예: swing, 스윙)"
              value={form.aliases}
              onChange={e => setForm(f => ({ ...f, aliases: e.target.value }))}
            />
            <input
              className="terms-form__input terms-form__input--desc"
              placeholder="설명 (예: 사내 메신저 시스템)"
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
            />
            <button className="terms-form__btn" type="submit" disabled={saving}>
              {saving ? '저장 중...' : '+ 등록'}
            </button>
          </div>
          {error && <div className="terms-form__error">{error}</div>}
        </form>

        {/* 테이블 */}
        <div className="terms-table-wrap">
          {loading ? (
            <div className="terms-empty">로딩 중...</div>
          ) : terms.length === 0 ? (
            <div className="terms-empty">등록된 용어가 없습니다.</div>
          ) : (
            <table className="terms-table">
              <thead>
                <tr>
                  <th>용어</th>
                  <th>별칭</th>
                  <th>설명</th>
                  <th>등록자</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {terms.map(t => (
                  <tr key={t.id}>
                    <td className="terms-table__term">{t.term}</td>
                    <td className="terms-table__aliases">
                      {(t.aliases || []).length > 0
                        ? t.aliases.join(', ')
                        : <span className="terms-table__none">—</span>}
                    </td>
                    <td className="terms-table__desc">{t.description}</td>
                    <td className="terms-table__by">{t.created_by}</td>
                    <td>
                      <button className="terms-table__del" onClick={() => handleDelete(t.id)}>삭제</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
