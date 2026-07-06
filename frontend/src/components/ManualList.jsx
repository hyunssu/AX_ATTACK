import ManualItem from './ManualItem'

export default function ManualList({ manuals, selectedManualId, onSelectManual }) {
  return (
    <aside className="manuals-sidebar">
      <h3 className="panel__title">매뉴얼 목록</h3>
      <div className="manual-list">
        {manuals.length === 0 && <p className="status-text">등록된 매뉴얼이 없습니다.</p>}
        {manuals.map((manual) => (
          <ManualItem
            key={manual.id}
            manual={manual}
            versionCount={manual.version_count}
            selected={selectedManualId === manual.id}
            onSelect={onSelectManual}
          />
        ))}
      </div>
    </aside>
  )
}
