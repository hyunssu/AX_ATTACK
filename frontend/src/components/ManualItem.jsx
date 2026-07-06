export default function ManualItem({ manual, versionCount, selected, onSelect }) {
  return (
    <div
      role="button"
      tabIndex={0}
      className={`manual-item${selected ? ' manual-item--selected' : ''}`}
      onClick={() => onSelect(manual.id)}
    >
      <div className="manual-item__title">{manual.title}</div>
      <div className="manual-item__meta">버전 {versionCount}개</div>
    </div>
  )
}
