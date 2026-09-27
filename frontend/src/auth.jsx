/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { fetchEmployeeMe, fetchSignupMeta } from './api'

const AuthContext = createContext(null)
const TOKEN_KEY = 'manual_system_token'
const USERNAME_KEY = 'manual_system_username'
const ROLE_KEY = 'manual_system_role'

function resolveEmployeeProfile(me, meta) {
  const position = meta.positions.find((p) => p.code === me.position_code)
  const permission = meta.permissions.find((p) => p.code === me.permission_code)
  const useEn = me.lang_code === 'EN'
  return {
    id: me.id,
    email: me.email,
    teamCode: me.team_code,
    positionCode: me.position_code,
    permissionCode: me.permission_code,
    langCode: me.lang_code,
    countries: me.countries || [],
    positionName: position ? (useEn ? position.name_en : position.name_ko) : me.position_code,
    permissionName: permission ? (useEn ? permission.name_en : permission.name_ko) : me.permission_code,
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [username, setUsername] = useState(() => localStorage.getItem(USERNAME_KEY))
  const [role, setRole] = useState(() => localStorage.getItem(ROLE_KEY))
  // employee_info 계정의 로그인 정보(언어코드에 따른 직급/권한 표시명 포함)를
  // 여기서 한 번만 들고 있고, 값이 바뀌면(마이페이지 수정 등) refreshEmployee()로
  // 갱신해 모든 화면(헤더 등)에 즉시 반영한다.
  const [employee, setEmployee] = useState(null)

  const refreshEmployee = useCallback(async () => {
    if (!localStorage.getItem(TOKEN_KEY)) {
      setEmployee(null)
      return
    }
    try {
      const [me, meta] = await Promise.all([fetchEmployeeMe(), fetchSignupMeta()])
      setEmployee(me ? resolveEmployeeProfile(me, meta) : null)
    } catch {
      setEmployee(null)
    }
  }, [])

  useEffect(() => {
    if (token) refreshEmployee()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function login(newToken, newUsername, newRole) {
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USERNAME_KEY, newUsername)
    localStorage.setItem(ROLE_KEY, newRole)
    setToken(newToken)
    setUsername(newUsername)
    setRole(newRole)
    refreshEmployee()
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USERNAME_KEY)
    localStorage.removeItem(ROLE_KEY)
    setToken(null)
    setUsername(null)
    setRole(null)
    setEmployee(null)
  }

  return (
    <AuthContext.Provider value={{ token, username, role, employee, refreshEmployee, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}
