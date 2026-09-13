/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)
const TOKEN_KEY = 'manual_system_token'
const USERNAME_KEY = 'manual_system_username'
const ROLE_KEY = 'manual_system_role'

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [username, setUsername] = useState(() => localStorage.getItem(USERNAME_KEY))
  const [role, setRole] = useState(() => localStorage.getItem(ROLE_KEY))

  function login(newToken, newUsername, newRole) {
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USERNAME_KEY, newUsername)
    localStorage.setItem(ROLE_KEY, newRole)
    setToken(newToken)
    setUsername(newUsername)
    setRole(newRole)
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USERNAME_KEY)
    localStorage.removeItem(ROLE_KEY)
    setToken(null)
    setUsername(null)
    setRole(null)
  }

  return (
    <AuthContext.Provider value={{ token, username, role, login, logout }}>
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
