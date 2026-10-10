import { NavLink, useNavigate } from 'react-router-dom'
import { checkpointAllRooms } from '../api'
import { useAuth } from '../auth'
import BrandMark from './BrandMark'

export default function Header() {
  const { employee, logout } = useAuth()
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
        <NavLink to="/mindmap" className="app-header__logo" aria-label="MANUAL로 이동">
          <BrandMark width={28} height={32} />
          <span>매뉴얼 관리 시스템</span>
        </NavLink>
        <nav className="app-header__nav">
          <NavLink
            to="/about"
            className={({ isActive }) => `app-header__nav-item${isActive ? ' active' : ''}`}
          >
            ABOUT US
          </NavLink>
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
            MANUAL
          </NavLink>
          <NavLink to="/faqs" className={({ isActive }) => `app-header__nav-item${isActive ? ' active' : ''}`}>
            FAQ
          </NavLink>
          <NavLink
            to="/terms"
            className={({ isActive }) => `app-header__nav-item${isActive ? ' active' : ''}`}
          >
            TERMS
          </NavLink>
        </nav>
        <div className="app-header__user">
          <span>
            {employee && (
              `${employee.id} · ${employee.permissionCode}(${employee.permissionName})`
            )}
          </span>
          {employee && (
            <NavLink to="/mypage" className="app-header__mypage">마이페이지</NavLink>
          )}
          <button type="button" className="app-header__logout" onClick={handleLogout}>로그아웃</button>
        </div>
      </div>
    </header>
  )
}
