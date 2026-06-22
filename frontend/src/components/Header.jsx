import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export default function Header() {
  const { username, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <div className="app-header__logo">매뉴얼 관리 시스템</div>
        <nav className="app-header__nav">
          <NavLink
            to="/manuals"
            className={({ isActive }) => `app-header__nav-item${isActive ? ' active' : ''}`}
          >
            매뉴얼
          </NavLink>
          <NavLink
            to="/qa"
            className={({ isActive }) => `app-header__nav-item${isActive ? ' active' : ''}`}
          >
            Q&A
          </NavLink>
        </nav>
        <div className="app-header__user">
          <span>{username}</span>
          <button type="button" className="app-header__logout" onClick={handleLogout}>로그아웃</button>
        </div>
      </div>
    </header>
  )
}
