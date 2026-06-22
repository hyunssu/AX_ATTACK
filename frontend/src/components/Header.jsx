export default function Header() {
  return (
    <header className="app-header">
      <div className="app-header__inner">
        <div className="app-header__logo">매뉴얼 관리 시스템</div>
        <nav className="app-header__nav">
          <span className="app-header__nav-item active">매뉴얼</span>
          <span className="app-header__nav-item">Q&A</span>
        </nav>
      </div>
    </header>
  )
}
