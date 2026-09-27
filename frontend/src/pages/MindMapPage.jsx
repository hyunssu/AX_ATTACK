import { useEffect, useRef, useState, useCallback } from 'react'
import { fetchManuals, fetchCategories, fetchCategoryFavorites, addCategoryFavorite, removeCategoryFavorite, quickCreateManual, listTrails, createTrail, renameTrail, deleteTrail, deleteManual, setManualSubCategory, dismissManualAiSuggestion, analyzeManualSections, confirmManualSections } from '../api'
import EditorPanel from '../components/EditorPanel'
import ManualSectionReviewModal from '../components/ManualSectionReviewModal'
import TermsModal from '../components/TermsModal'
import './MindMapPage.css'

const _DEFAULT_TAXONOMY = {
  '여신': { color: '#4a7fcb', light: '#daeaf9', en: 'Credit',   team: null, canEdit: false },
  '수신': { color: '#4fad8a', light: '#cceee0', en: 'Deposit',  team: null, canEdit: false },
  '외환': { color: '#8b72d4', light: '#e2dcf8', en: 'FX',       team: null, canEdit: false },
  '자금': { color: '#d4843f', light: '#f8e4ca', en: 'Treasury', team: null, canEdit: false },
  '카드': { color: '#d45e6e', light: '#f9d5d8', en: 'Card',     team: null, canEdit: false },
  '고객': { color: '#5b9fd4', light: '#cce2f8', en: 'Customer', team: null, canEdit: false },
  '기타': { color: '#8a9bb0', light: '#d8dee4', en: 'Others',   team: null, canEdit: false },
}
const _DEFAULT_CATS = Object.keys(_DEFAULT_TAXONOMY)


export default function MindMapPage() {
  const [manuals, setManuals] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedCat, setSelectedCat] = useState(null)
  const [selectedManual, setSelectedManual] = useState(null)
  const [customTrails, setCustomTrails] = useState([])
  const [taxonomy, setTaxonomy] = useState(_DEFAULT_TAXONOMY)
  const [cats, setCats] = useState(_DEFAULT_CATS)
  const [catFavNames, setCatFavNames] = useState(new Set())
  const [viewMode, setViewMode] = useState('all') // 'all' | 'favorites'
  const [isEditorWide, setIsEditorWide] = useState(false)
  const [termsModal, setTermsModal] = useState(null) // null | { initialTerm? }

  const refreshManuals = useCallback(() => {
    fetchManuals()
      .then(data => setManuals(Array.isArray(data) ? data : []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    Promise.all([
      fetchManuals().catch(() => []),
      fetchCategories().catch(() => []),
      fetchCategoryFavorites().catch(() => []),
    ]).then(([manualsData, catData, favNames]) => {
      setManuals(Array.isArray(manualsData) ? manualsData : [])
      if (Array.isArray(catData) && catData.length > 0) {
        const tax = {}
        catData.forEach(c => {
          tax[c.name] = {
            color: c.color,
            light: c.color_light,
            en: c.name_en || c.name,
            team: c.team_name_ko || null,
            canEdit: !!c.can_edit,
          }
        })
        setTaxonomy(tax)
        setCats(catData.map(c => c.name))
      }
      if (Array.isArray(favNames)) setCatFavNames(new Set(favNames))
      setLoading(false)
    })

    const pollId = setInterval(() => {
      fetchManuals()
        .then(data => setManuals(prev => {
          if (!Array.isArray(data)) return prev
          // locked_by 변경된 항목만 반영 (불필요한 리렌더 최소화)
          const hasChange = data.some((next, i) => {
            const cur = prev.find(p => p.id === next.id)
            return !cur || cur.locked_by !== next.locked_by || cur.locked_at !== next.locked_at
          }) || prev.some(p => !data.find(d => d.id === p.id))
          return hasChange ? data : prev
        }))
        .catch(() => {})
    }, 30000)

    return () => clearInterval(pollId)
  }, [])

  const handleToggleCatFavorite = useCallback(async (catName) => {
    const isFav = catFavNames.has(catName)
    setCatFavNames(prev => {
      const next = new Set(prev)
      isFav ? next.delete(catName) : next.add(catName)
      return next
    })
    try {
      isFav ? await removeCategoryFavorite(catName) : await addCategoryFavorite(catName)
    } catch {
      setCatFavNames(prev => {
        const next = new Set(prev)
        isFav ? next.add(catName) : next.delete(catName)
        return next
      })
    }
  }, [catFavNames])

  useEffect(() => {
    if (!selectedCat) { setCustomTrails([]); return }
    listTrails(selectedCat)
      .then(trails => setCustomTrails(Array.isArray(trails) ? trails.filter(t => t?.name && t.name !== 'null') : []))
      .catch(() => setCustomTrails([]))
  }, [selectedCat])

  const handleManualAdd = useCallback(async (title, subCategory) => {
    const realSub = subCategory === '기타' ? null : subCategory
    const newManual = await quickCreateManual(title, [selectedCat], realSub)
    refreshManuals()
    return newManual
  }, [selectedCat, refreshManuals])

  const handleAddTrail = useCallback(async (name, nameEn = '') => {
    await createTrail(selectedCat, name, nameEn)
    setCustomTrails(prev => prev.some(t => t.name === name) ? prev : [...prev, { name, name_en: nameEn || null }])
  }, [selectedCat])

  const handleRenameTrail = useCallback(async (oldName, newName, newNameEn = '') => {
    await renameTrail(selectedCat, oldName, newName, newNameEn)
    setCustomTrails(prev => prev.map(t => t.name === oldName ? { name: newName, name_en: newNameEn || t.name_en } : t))
    refreshManuals()
  }, [selectedCat, refreshManuals])

  const handleDeleteTrail = useCallback(async (name) => {
    await deleteTrail(selectedCat, name)
    setCustomTrails(prev => prev.filter(t => t.name !== name))
    refreshManuals()
  }, [selectedCat, refreshManuals])

  const handleDeleteManual = useCallback(async (manual) => {
    await deleteManual(manual.id)
    if (selectedManual?.id === manual.id) setSelectedManual(null)
    refreshManuals()
  }, [selectedManual, refreshManuals])

  const handleMoveManual = useCallback(async (manual, newSub) => {
    const realSub = newSub === '기타' ? null : newSub
    const currentSub = manual.sub_category || '기타'
    if (currentSub === newSub) return
    try {
      await setManualSubCategory(manual.id, realSub)
      refreshManuals()
    } catch {}
  }, [refreshManuals])

  const handleAcceptAi = useCallback(async (manual) => {
    await setManualSubCategory(manual.id, manual.ai_suggested_sub)
    refreshManuals()
  }, [refreshManuals])

  const handleRejectAi = useCallback(async (manual) => {
    await dismissManualAiSuggestion(manual.id)
    refreshManuals()
  }, [refreshManuals])

  const handleUploaded = useCallback(() => {
    refreshManuals()
    if (selectedCat) {
      listTrails(selectedCat)
        .then(trails => setCustomTrails(Array.isArray(trails) ? trails.filter(t => t?.name && t.name !== 'null') : []))
        .catch(() => {})
    }
  }, [refreshManuals, selectedCat])

  const visibleCats = viewMode === 'favorites'
    ? cats.filter(c => catFavNames.has(c))
    : cats

  const byCategory = cats.reduce((acc, cat) => {
    acc[cat] = manuals.filter(m => Array.isArray(m.categories) && m.categories[0] === cat)
    return acc
  }, {})

  const groupBySub = (catManuals, extraTrails = []) => {
    const trailNames = extraTrails.map(t => t.name)
    const grouped = {}
    const unsorted = []
    for (const m of catManuals) {
      const sub = m.sub_category
      if (sub && trailNames.includes(sub)) {
        if (!grouped[sub]) grouped[sub] = []
        grouped[sub].push(m)
      } else {
        unsorted.push(m)
      }
    }
    // DB 트레일 순서 유지 (빈 컬럼도 포함), trail 객체 전달
    const result = extraTrails.map(trail => ({ sub: trail.name, subEn: trail.name_en, items: grouped[trail.name] || [] }))
    if (unsorted.length) result.push({ sub: '기타', subEn: 'Others', items: unsorted })
    return result
  }

  // 패널에 표시할 카드 순서: 선택된 것 맨 위, 나머지 아래
  const panelCats = selectedCat
    ? [selectedCat, ...visibleCats.filter(c => c !== selectedCat)]
    : visibleCats

  return (
    <div className="mm-page">
      <div className="mm-toolbar">
        <span className="mm-toolbar__title">MANUAL</span>
        <div className="mm-toolbar__view-tabs">
          <button
            className={`mm-toolbar__view-tab${viewMode === 'all' ? ' mm-toolbar__view-tab--active' : ''}`}
            onClick={() => setViewMode('all')}
          >OVERVIEW</button>
          <button
            className={`mm-toolbar__view-tab${viewMode === 'favorites' ? ' mm-toolbar__view-tab--active' : ''}`}
            onClick={() => setViewMode('favorites')}
          >★ FAVORITES</button>
        </div>
      </div>

      {termsModal && (
        <TermsModal
          initialTerm={termsModal.initialTerm}
          onClose={() => setTermsModal(null)}
        />
      )}

      {loading ? (
        <div className="mm-loading">매뉴얼을 불러오는 중...</div>
      ) : (
        <div className="mm-body">

          {/* 왼쪽 패널 — 카드 클릭 시 슬라이드 인 */}
          <div className={`mm-panel${selectedCat ? ' mm-panel--open' : ''}`}>
            <button className="mm-panel__close" onClick={() => setSelectedCat(null)} title="닫기">✕</button>
            <div className="mm-panel__cards">
              {panelCats.map(cat => (
                <PanelCard
                  key={cat}
                  cat={cat}
                  tax={taxonomy[cat] || { color: '#8a9bb0', light: '#d8dee4', en: cat, team: null, canEdit: false }}
                  count={(byCategory[cat] || []).length}
                  selected={cat === selectedCat}
                  isFavorited={catFavNames.has(cat)}
                  onClick={() => setSelectedCat(cat === selectedCat ? null : cat)}
                  onToggleFavorite={handleToggleCatFavorite}
                />
              ))}
            </div>
          </div>

          {/* 메인 영역 (오른쪽) */}
          <div className={`mm-main${isEditorWide ? ' mm-main--shrunk' : ''}`}>
            {selectedCat ? (
              <TrelloBoard
                cat={selectedCat}
                tax={taxonomy[selectedCat] || { color: '#8a9bb0', light: '#d8dee4', en: selectedCat, team: null, canEdit: false }}
                sections={groupBySub(byCategory[selectedCat] || [], customTrails)}
                onManualSelect={setSelectedManual}
                onAdd={handleManualAdd}
                onAddTrail={handleAddTrail}
                onRenameTrail={handleRenameTrail}
                onDeleteTrail={handleDeleteTrail}
                onMoveManual={handleMoveManual}
                onAcceptAi={handleAcceptAi}
                onRejectAi={handleRejectAi}
                customTrails={customTrails}
                onUploaded={handleUploaded}
                currentUser={localStorage.getItem('manual_system_username') || ''}
              />
            ) : (
              <CardView byCategory={byCategory} cats={visibleCats} taxonomy={taxonomy} onSelect={setSelectedCat} catFavNames={catFavNames} onToggleCatFavorite={handleToggleCatFavorite} />
            )}
          </div>

          {/* 에디터 패널 (오른쪽 슬라이드) */}
          <div className={`mm-editor${selectedManual ? ' mm-editor--open' : ''}${selectedManual && isEditorWide ? ' mm-editor--wide' : ''}`}>
            <EditorPanel
              manual={selectedManual}
              canEdit={!!taxonomy[selectedManual?.categories?.[0]]?.canEdit}
              onClose={() => { setSelectedManual(null); setIsEditorWide(false) }}
              isWide={isEditorWide}
              onToggleWide={() => setIsEditorWide(w => !w)}
              onOpenTerms={(initialTerm) => setTermsModal({ initialTerm })}
              onLockChange={refreshManuals}
            />
          </div>

        </div>
      )}
    </div>
  )
}

/* ── Category card (카드/맵 뷰 메인 영역용) ─────── */
function CategoryCard({ cat, tax, count, onClick, isFavorited, onToggleFavorite }) {
  return (
    <div
      className="mm-cat-card"
      style={{ '--cat-color': tax.color, '--cat-light': tax.light }}
      onClick={onClick}
    >
      <div className="mm-cat-card__accent" />
      {onToggleFavorite && (
        <button
          className={`mm-cat-card__fav${isFavorited ? ' mm-cat-card__fav--on' : ''}`}
          title={isFavorited ? '즐겨찾기 해제' : '즐겨찾기'}
          onClick={e => { e.stopPropagation(); onToggleFavorite(cat) }}
        >{isFavorited ? '★' : '☆'}</button>
      )}
      <div className="mm-cat-card__ko">{cat}</div>
      <div className="mm-cat-card__team">{tax.team || '관리자 전용'}</div>
      <div className="mm-cat-card__count">{count}개 매뉴얼</div>
    </div>
  )
}

/* ── 오른쪽 패널 카드 ──────────────────────────── */
function PanelCard({ cat, tax, count, selected, onClick, isFavorited, onToggleFavorite }) {
  return (
    <div
      className={`mm-panel-card${selected ? ' mm-panel-card--selected' : ''}`}
      style={{ '--cat-color': tax.color, '--cat-light': tax.light }}
      onClick={onClick}
    >
      <div className="mm-panel-card__accent" />
      <div className="mm-panel-card__body">
        <div className="mm-panel-card__ko">{cat}</div>
        <div className="mm-panel-card__team">{tax.team || '관리자 전용'}</div>
        <div className="mm-panel-card__count">{count}개</div>
      </div>
      {onToggleFavorite && (
        <button
          className={`mm-panel-card__fav${isFavorited ? ' mm-panel-card__fav--on' : ''}`}
          title={isFavorited ? '즐겨찾기 해제' : '즐겨찾기'}
          onClick={e => { e.stopPropagation(); onToggleFavorite(cat) }}
        >{isFavorited ? '★' : '☆'}</button>
      )}
    </div>
  )
}

/* ── 카드 그리드 뷰 ─────────────────────────────── */
function CardView({ byCategory, cats, taxonomy, onSelect, catFavNames, onToggleCatFavorite }) {
  return (
    <div className="mm-card-grid">
      {cats.length === 0
        ? <div className="mm-card-grid__empty">즐겨찾기한 업무가 없습니다.</div>
        : cats.map(cat => {
          const tax = taxonomy[cat] || { color: '#8a9bb0', light: '#d8dee4', en: cat, team: null, canEdit: false }
          return (
            <CategoryCard
              key={cat}
              cat={cat}
              tax={tax}
              count={(byCategory[cat] || []).length}
              isFavorited={catFavNames?.has(cat)}
              onClick={() => onSelect(cat)}
              onToggleFavorite={onToggleCatFavorite}
            />
          )
        })
      }
    </div>
  )
}

/* ── Trello 보드 ─────────────────────────────────── */
function TrelloBoard({ cat, tax, sections, onManualSelect, onAdd, onAddTrail, onRenameTrail, onDeleteTrail, onMoveManual, onAcceptAi, onRejectAi, customTrails, onUploaded, currentUser }) {
  const [uploadOpen, setUploadOpen] = useState(false)
  const [orderedSections, setOrderedSections] = useState(sections)
  const dragRef = useRef(null)
  const canEdit = !!tax.canEdit

  useEffect(() => {
    const prevSubs = new Set(orderedSections.map(s => s.sub))
    const newSubs = new Set(sections.map(s => s.sub))
    const setsEqual = prevSubs.size === newSubs.size && [...prevSubs].every(s => newSubs.has(s))
    if (!setsEqual) {
      setOrderedSections(sections)
    } else {
      setOrderedSections(prev => prev.map(ps => ({
        ...ps,
        items: sections.find(s => s.sub === ps.sub)?.items ?? ps.items,
      })))
    }
  }, [sections])

  const handleTrailReorder = useCallback((fromSub, toSub, insertAfter) => {
    setOrderedSections(prev => {
      const fromIdx = prev.findIndex(s => s.sub === fromSub)
      const toIdx = prev.findIndex(s => s.sub === toSub)
      if (fromIdx === -1 || toIdx === -1 || fromIdx === toIdx) return prev
      const next = [...prev]
      const [moved] = next.splice(fromIdx, 1)
      const newToIdx = next.findIndex(s => s.sub === toSub)
      next.splice(insertAfter ? newToIdx + 1 : newToIdx, 0, moved)
      return next
    })
  }, [])

  function handleUploaded() {
    setUploadOpen(false)
    onUploaded()
  }

  return (
    <div className="mm-trello" style={{ '--cat-color': tax.color, '--cat-light': tax.light }}>
      <div className="mm-trello__header">
        <span className="mm-trello__ko">{cat}</span>
        <span className="mm-trello__team">{tax.team || '관리자 전용'}</span>
        <span className="mm-trello__total">{sections.reduce((s, g) => s + g.items.length, 0)}개 매뉴얼</span>
        {canEdit ? (
          <button className="mm-trello__upload-btn" onClick={() => setUploadOpen(true)}>
            ↑ 파일 업로드
          </button>
        ) : (
          <span className="mm-trello__readonly-badge" title="이 카드는 소속 팀만 수정할 수 있습니다">👁 읽기 전용</span>
        )}
      </div>
      <div className="mm-trello__board">
        {orderedSections.length === 0 ? (
          canEdit && <TrelloAddColumn color={tax.color} sub={null} onAdd={onAdd} />
        ) : (
          orderedSections.map(({ sub, subEn, items }) => (
            <TrelloColumn
              key={sub}
              sub={sub}
              subEn={subEn}
              items={items}
              color={tax.color}
              dragRef={dragRef}
              onManualSelect={onManualSelect}
              onAdd={onAdd}
              onRenameTrail={onRenameTrail}
              onDeleteTrail={onDeleteTrail}
              onMoveManual={onMoveManual}
              onTrailReorder={handleTrailReorder}
              onAcceptAi={onAcceptAi}
              onRejectAi={onRejectAi}
              currentUser={currentUser}
              canEdit={canEdit}
            />
          ))
        )}
        {canEdit && <NewTrailColumn color={tax.color} onAddTrail={onAddTrail} />}
      </div>
      {uploadOpen && (
        <TrelloUploadModal cat={cat} tax={tax} customTrails={customTrails} onClose={() => setUploadOpen(false)} onCreated={handleUploaded} />
      )}
    </div>
  )
}

/* ── 파일 드래그앤드롭 존 ──────────────────────────────── */
function FileDropZone({ file, color, onChange }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  function pickFile(f) {
    if (!f || !f.name.match(/\.(pdf|md)$/i)) return
    onChange(f)
  }

  return (
    <div
      className={`mm-drop-zone${dragging ? ' mm-drop-zone--drag' : ''}${file ? ' mm-drop-zone--filled' : ''}`}
      style={{ '--cat-color': color }}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0]) }}
      onClick={() => !file && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.md,text/markdown"
        style={{ display: 'none' }}
        onChange={e => pickFile(e.target.files[0])}
      />
      {file ? (
        <div className="mm-drop-zone__file">
          <span className="mm-drop-zone__file-icon">📄</span>
          <span className="mm-drop-zone__file-name">{file.name}</span>
          <button className="mm-drop-zone__clear" title="파일 제거"
            onClick={e => { e.stopPropagation(); onChange(null) }}>✕</button>
        </div>
      ) : (
        <>
          <div className="mm-drop-zone__icon">↑</div>
          <div className="mm-drop-zone__main">PDF 또는 Markdown 파일을 드래그하거나</div>
          <button className="mm-drop-zone__pick-btn"
            onClick={e => { e.stopPropagation(); inputRef.current?.click() }}>파일 선택</button>
          <div className="mm-drop-zone__hint">.pdf · .md</div>
        </>
      )}
    </div>
  )
}

/* ── MindMap 전용 파일 업로드 모달 ─────────────────────── */
function TrelloUploadModal({ cat, tax, customTrails, onClose, onCreated }) {
  const [file, setFile] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [status, setStatus] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [sections, setSections] = useState([])
  const [reviewing, setReviewing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [confirmError, setConfirmError] = useState('')
  const fileUrlRef = useRef(null)

  useEffect(() => () => { if (fileUrlRef.current) URL.revokeObjectURL(fileUrlRef.current) }, [])

  const availableSubs = customTrails.map(t => t.name)

  function handleFileChange(newFile) {
    if (fileUrlRef.current) { URL.revokeObjectURL(fileUrlRef.current); fileUrlRef.current = null }
    setFile(newFile)
    setStatus('')
    setAnalysis(null)
    setSections([])
    if (newFile) fileUrlRef.current = URL.createObjectURL(newFile)
  }

  async function handleAnalyze() {
    if (!file) return
    setAnalyzing(true)
    setStatus('')
    try {
      const result = await analyzeManualSections(file, cat)
      setAnalysis(result)
      setSections(result.sections)
      setReviewing(true)
    } catch (err) {
      setStatus(`오류: ${err.message}`)
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleConfirm() {
    if (!analysis) return
    setConfirming(true)
    setConfirmError('')
    try {
      // deploy: false — 카드(초안)만 생성한다. 실제 청킹/임베딩은 카드에서
      // 내용 확인 → AI 검증을 마친 뒤 "운영반영" 버튼으로 별도 실행된다.
      await confirmManualSections(analysis, sections, 'ko', false)
      setReviewing(false)
      onCreated()
    } catch (err) {
      setConfirmError(`오류: ${err.message}`)
    } finally {
      setConfirming(false)
    }
  }

  const outsideClick = e => {
    if (e.target === e.currentTarget && !reviewing) onClose()
  }

  return (
    <div className="modal-overlay" onClick={outsideClick}>
      <div className="modal-card modal-card--xl mm-upload-modal"
        style={{ '--cat-color': tax.color, '--cat-light': tax.light }}>

        <div className="mm-upload-modal__head">
          <div>
            <div className="mm-upload-modal__cat-en">{tax.en}</div>
            <div className="mm-upload-modal__cat-ko">{cat} — 파일 업로드</div>
          </div>
          <button className="mm-upload-modal__close" onClick={onClose} title="닫기">✕</button>
        </div>

        <p className="mm-upload-modal__desc">
          파일을 분석하면 섹션별로 <strong>{cat}</strong> 소분류를 자동으로 추천합니다.
          <strong> {cat} 업무와 관련 없는</strong> 섹션은 검토 화면에서 기본적으로 제외됩니다.
        </p>

        <FileDropZone file={file} color={tax.color} onChange={handleFileChange} />

        <div className="mm-upload-modal__actions">
          {file && (
            <button className="btn btn--ghost"
              onClick={() => fileUrlRef.current && window.open(fileUrlRef.current, '_blank')}>
              원문 보기
            </button>
          )}
          <button
            className="mm-upload-modal__analyze-btn"
            style={{ background: tax.color }}
            onClick={handleAnalyze}
            disabled={!file || analyzing}
          >
            {analyzing ? '분석 중…' : '분석하기 →'}
          </button>
        </div>

        {status && <div className="status-text">{status}</div>}

        {reviewing && (
          <ManualSectionReviewModal
            sections={sections}
            onChange={setSections}
            onConfirm={handleConfirm}
            onCancel={() => { setReviewing(false); setConfirmError(''); setAnalysis(null); setSections([]) }}
            confirming={confirming}
            error={confirmError}
            contextCategory={cat}
            availableSubs={availableSubs}
          />
        )}
      </div>
    </div>
  )
}

function TrelloColumn({ sub, subEn, items, color, dragRef, onManualSelect, onAdd, onRenameTrail, onDeleteTrail, onMoveManual, onTrailReorder, onAcceptAi, onRejectAi, currentUser, canEdit }) {
  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [editingTitle, setEditingTitle] = useState(false)
  const [editTitle, setEditTitle] = useState(sub)
  const [editTitleEn, setEditTitleEn] = useState(subEn || '')
  const [deleting, setDeleting] = useState(false)
  const [dragState, setDragState] = useState('idle') // 'idle' | 'card-over' | 'trail-before' | 'trail-after'
  const dragPosition = useRef('before')
  const inputRef = useRef(null)
  const editInputRef = useRef(null)

  useEffect(() => { if (adding) inputRef.current?.focus() }, [adding])
  useEffect(() => { if (editingTitle) editInputRef.current?.focus() }, [editingTitle])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!title.trim() || submitting) return
    setSubmitting(true)
    try { await onAdd(title.trim(), sub) } catch {}
    setTitle('')
    setAdding(false)
    setSubmitting(false)
  }

  const handleRenameSubmit = async (e) => {
    e?.preventDefault?.()
    const trimmed = editTitle.trim()
    setEditingTitle(false)
    if (!trimmed || trimmed === sub) { setEditTitle(sub); return }
    try { await onRenameTrail(sub, trimmed, editTitleEn.trim()) } catch { setEditTitle(sub); setEditTitleEn(subEn || '') }
  }

  const handleDeleteTrail = async () => {
    if (!window.confirm(`"${sub}" 트레일을 삭제할까요?\n해당 트레일의 매뉴얼은 미분류로 이동됩니다.`)) return
    setDeleting(true)
    try { await onDeleteTrail(sub) } catch { setDeleting(false) }
  }

  const handleDragOver = (e) => {
    if (!canEdit) return
    const drag = dragRef.current
    if (!drag) return
    if (drag.type === 'card') {
      const currentSub = drag.manual.sub_category || '기타'
      if (currentSub !== sub) {
        e.preventDefault()
        setDragState('card-over')
      }
    } else if (drag.type === 'trail' && drag.sub !== sub) {
      e.preventDefault()
      const rect = e.currentTarget.getBoundingClientRect()
      const after = e.clientX > rect.left + rect.width / 2
      dragPosition.current = after ? 'after' : 'before'
      setDragState(after ? 'trail-after' : 'trail-before')
    }
  }

  const handleDragLeave = (e) => {
    if (!e.currentTarget.contains(e.relatedTarget)) setDragState('idle')
  }

  const handleDrop = (e) => {
    e.preventDefault()
    if (!canEdit) return
    const drag = dragRef.current
    const state = dragState
    setDragState('idle')
    if (!drag) return
    dragRef.current = null
    if (drag.type === 'card' && state === 'card-over') {
      onMoveManual(drag.manual, sub)
    } else if (drag.type === 'trail' && drag.sub !== sub) {
      onTrailReorder(drag.sub, sub, dragPosition.current === 'after')
    }
  }

  const isRealTrail = sub !== '기타'
  const colClass = ['mm-trello-col',
    dragState === 'card-over' ? 'mm-trello-col--card-over' : '',
    dragState === 'trail-before' ? 'mm-trello-col--trail-before' : '',
    dragState === 'trail-after' ? 'mm-trello-col--trail-after' : '',
  ].filter(Boolean).join(' ')

  return (
    <div
      className={colClass}
      style={{ '--col-color': color }}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="mm-trello-col__header" style={{ color }}>
        {isRealTrail && !editingTitle && canEdit && (
          <span
            className="mm-trello-col__drag-handle"
            draggable={true}
            title="드래그하여 순서 변경"
            onDragStart={e => {
              e.stopPropagation()
              dragRef.current = { type: 'trail', sub }
              e.dataTransfer.effectAllowed = 'move'
            }}
            onDragEnd={() => { dragRef.current = null }}
          >⠿</span>
        )}
        {editingTitle ? (
          <form style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }} onSubmit={handleRenameSubmit}>
            <input
              ref={editInputRef}
              className="mm-trello-col__name-input"
              value={editTitle}
              onChange={e => setEditTitle(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Escape') { setEditingTitle(false); setEditTitle(sub); setEditTitleEn(subEn || '') }
                if (e.key === 'Enter') handleRenameSubmit()
              }}
              placeholder="한글명"
            />
            <input
              className="mm-trello-col__name-input"
              value={editTitleEn}
              onChange={e => setEditTitleEn(e.target.value)}
              onBlur={handleRenameSubmit}
              onKeyDown={e => {
                if (e.key === 'Escape') { setEditingTitle(false); setEditTitle(sub); setEditTitleEn(subEn || '') }
                if (e.key === 'Enter') handleRenameSubmit()
              }}
              placeholder="English name (optional)"
            />
          </form>
        ) : (
          <span
            className="mm-trello-col__name"
            title={isRealTrail && canEdit ? '더블클릭으로 이름 수정' : undefined}
            onDoubleClick={() => { if (isRealTrail && canEdit) { setEditingTitle(true); setEditTitle(sub); setEditTitleEn(subEn || '') } }}
          >
            {sub}{subEn ? <span className="mm-trello-col__name-en"> · {subEn}</span> : null}
          </span>
        )}
        <span className="mm-trello-col__count">{items.length}</span>
        {isRealTrail && !editingTitle && items.length === 0 && canEdit && (
          <button
            className="mm-trello-col__delete"
            title="트레일 삭제"
            onClick={handleDeleteTrail}
            disabled={deleting}
          >✕</button>
        )}
      </div>
      <div className="mm-trello-col__cards">
        {items.map(m => (
          <TrelloCard key={m.id} manual={m} color={color} dragRef={dragRef} onClick={() => onManualSelect(m)} onAcceptAi={onAcceptAi} onRejectAi={onRejectAi} currentUser={currentUser} canEdit={canEdit} />
        ))}
      </div>
      {!canEdit ? null : adding ? (
        <form className="mm-trello-add-form" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            className="mm-trello-add-input"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="제목 입력..."
            onKeyDown={e => e.key === 'Escape' && (setTitle(''), setAdding(false))}
          />
          <div className="mm-trello-add-actions">
            <button type="submit" className="mm-trello-add-btn" style={{ background: color }} disabled={submitting}>추가</button>
            <button type="button" className="mm-trello-cancel-btn" onClick={() => { setTitle(''); setAdding(false) }}>✕</button>
          </div>
        </form>
      ) : (
        <button className="mm-trello-col__add" style={{ '--col-color': color }} onClick={() => setAdding(true)}>
          + 추가
        </button>
      )}
    </div>
  )
}

/* 빈 보드 또는 새 그룹 추가용 컬럼 */
function TrelloAddColumn({ color, sub, onAdd }) {
  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => { if (adding) inputRef.current?.focus() }, [adding])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!title.trim() || submitting) return
    setSubmitting(true)
    try { await onAdd(title.trim(), sub) } catch {}
    setTitle('')
    setAdding(false)
    setSubmitting(false)
  }

  return (
    <div className="mm-trello-col mm-trello-col--empty">
      {adding ? (
        <form className="mm-trello-add-form mm-trello-add-form--top" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            className="mm-trello-add-input"
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="제목 입력..."
            onKeyDown={e => e.key === 'Escape' && (setTitle(''), setAdding(false))}
          />
          <div className="mm-trello-add-actions">
            <button type="submit" className="mm-trello-add-btn" style={{ background: color }} disabled={submitting}>추가</button>
            <button type="button" className="mm-trello-cancel-btn" onClick={() => { setTitle(''); setAdding(false) }}>✕</button>
          </div>
        </form>
      ) : (
        <button className="mm-trello-col__add mm-trello-col__add--empty" style={{ '--col-color': color }} onClick={() => setAdding(true)}>
          + 첫 번째 매뉴얼 추가
        </button>
      )}
    </div>
  )
}

/* ── 새 트레일(컬럼) 추가 버튼 ──────────────────────── */
function NewTrailColumn({ color, onAddTrail }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [nameEn, setNameEn] = useState('')
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  useEffect(() => { if (open) inputRef.current?.focus() }, [open])

  const handleClose = () => { setName(''); setNameEn(''); setError(''); setOpen(false) }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setError('')
    try {
      await onAddTrail(name.trim(), nameEn.trim())
      handleClose()
    } catch (err) {
      setError(err.message || '트레일 생성에 실패했습니다.')
    }
  }

  return (
    <div className="mm-trello-new-trail">
      {open ? (
        <form className="mm-trello-add-form mm-trello-add-form--top" onSubmit={handleSubmit}>
          <input
            ref={inputRef}
            className="mm-trello-add-input"
            value={name}
            onChange={e => { setName(e.target.value); setError('') }}
            placeholder="트레일 이름 (한글)..."
            onKeyDown={e => e.key === 'Escape' && handleClose()}
          />
          <input
            className="mm-trello-add-input"
            value={nameEn}
            onChange={e => setNameEn(e.target.value)}
            placeholder="English name (optional)"
            onKeyDown={e => e.key === 'Escape' && handleClose()}
          />
          {error && <div className="mm-trello-add-error">{error}</div>}
          <div className="mm-trello-add-actions">
            <button type="submit" className="mm-trello-add-btn" style={{ background: color }}>만들기</button>
            <button type="button" className="mm-trello-cancel-btn" onClick={handleClose}>✕</button>
          </div>
        </form>
      ) : (
        <button className="mm-trello-new-trail__btn" style={{ '--col-color': color }} onClick={() => setOpen(true)}>
          + 새 트레일
        </button>
      )}
    </div>
  )
}

function TrelloCard({ manual, color, dragRef, onClick, onAcceptAi, onRejectAi, currentUser, canEdit }) {
  const [dragging, setDragging] = useState(false)
  const date = manual.created_at
    ? new Date(manual.created_at).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
    : ''
  const isLockedByMe = manual.locked_by && manual.locked_by === currentUser
  const isLockedByOther = manual.locked_by && manual.locked_by !== currentUser

  return (
    <div
      className={`mm-trello-card${dragging ? ' mm-trello-card--dragging' : ''}${isLockedByOther ? ' mm-trello-card--locked' : ''}`}
      style={{ '--cat-color': color }}
      draggable={canEdit}
      onDragStart={e => {
        if (!canEdit) return
        e.stopPropagation()
        setDragging(true)
        dragRef.current = { type: 'card', manual }
        e.dataTransfer.effectAllowed = 'move'
      }}
      onDragEnd={() => { setDragging(false); dragRef.current = null }}
      onClick={onClick}
    >
      <div className="mm-trello-card__bar" />
      <div className="mm-trello-card__title">{manual.title}</div>
      {manual.ai_suggested_sub && (
        <div className="mm-ai-badge" onClick={e => e.stopPropagation()}>
          <span className="mm-ai-badge__label">AI 추천: {manual.ai_suggested_sub}</span>
          {canEdit && <button className="mm-ai-badge__accept" onClick={() => onAcceptAi(manual)} title="수락">✓</button>}
          {canEdit && <button className="mm-ai-badge__reject" onClick={() => onRejectAi(manual)} title="거절">✕</button>}
        </div>
      )}
      <div className="mm-trello-card__footer">
        {date && <span className="mm-trello-card__date">{date}</span>}
        {isLockedByMe && (
          <span className="mm-trello-card__lock mm-trello-card__lock--me" title="내가 편집 중">🔒 편집 중</span>
        )}
        {isLockedByOther && (
          <span className="mm-trello-card__lock mm-trello-card__lock--other" title={`${manual.locked_by}님이 편집 중`}>
            🔒 {manual.locked_by}
          </span>
        )}
      </div>
    </div>
  )
}
