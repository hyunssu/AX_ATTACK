export default function ManualItem({ manual, versionCount, onSelect }) {
  return (
    <div className="manual-card" role="button" tabIndex={0} onClick={onSelect}>
      <div className="manual-card__thumb" aria-hidden="true">{manual.title.charAt(0)}</div>
      <div className="manual-card__top">
        <div className="eyebrow">DOCUMENT</div>
        {manual.categories?.map((category) => (
          <span key={category} className="manual-card__category">{category}</span>
        ))}
      </div>
      <div className="manual-card__title">{manual.title}</div>
      <div className="manual-card__meta">버전 {versionCount}개</div>
      <div className="manual-card__link">자세히 보기 →</div>
    </div>
  )
}
