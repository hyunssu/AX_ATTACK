import { NavLink, useNavigate } from 'react-router-dom'
import { checkpointAllRooms } from '../api'
import { useAuth } from '../auth'

export default function Header() {
  const { username, role, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    try {
      await checkpointAllRooms()
    } finally {
      logout()
      navigate('/login')
    }
  }

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <div className="app-header__logo">매뉴얼 관리 시스템</div>
        <nav className="app-header__nav">
          <NavLink
            to="/about"
            className={({ isActive }) => `app-header__nav-item${isActive ? ' active' : ''}`}
          >
            ABOUT US
          </NavLink>
          <NavLink
            to="/manuals"
            className={({ isActive }) => `app-header__nav-item${isActive ? ' active' : ''}`}
          >
            MANUAL
          </NavLink>
          {['Admin', 'Developer'].includes(role) && (
            <NavLink
              to="/faqs"
              className={({ isActive }) => `app-header__nav-item${isActive ? ' active' : ''}`}
            >
              FAQ REVIEW
            </NavLink>
          )}
          <NavLink
            to="/qa"
            className={({ isActive }) => `app-header__nav-item${isActive ? ' active' : ''}`}
          >
            ASK AI
          </NavLink>
          <NavLink
            to="/mindmap"
            className={({ isActive }) => `app-header__nav-item${isActive ? ' active' : ''}`}
          >
            MIND MAP
          </NavLink>
        </nav>
        <div className="app-header__user">
          <span>{username}{role ? ` · ${role}` : ''}</span>
          <button type="button" className="app-header__logout" onClick={handleLogout}>로그아웃</button>
        </div>
      </div>
    </header>
  )
}
