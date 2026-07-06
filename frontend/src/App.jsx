import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import Header from './components/Header'
import LoginPage from './pages/LoginPage'
import ManualRegisterPage from './pages/ManualRegisterPage'
import ManualsPage from './pages/ManualsPage'
import QAPage from './pages/QAPage'
import './App.css'

function ProtectedLayout({ children }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  return (
    <>
      <Header />
      {children}
    </>
  )
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/manuals"
        element={(
          <ProtectedLayout>
            <ManualsPage />
          </ProtectedLayout>
        )}
      />
      <Route
        path="/manuals/new"
        element={(
          <ProtectedLayout>
            <ManualRegisterPage />
          </ProtectedLayout>
        )}
      />
      <Route
        path="/qa"
        element={(
          <ProtectedLayout>
            <QAPage />
          </ProtectedLayout>
        )}
      />
      <Route path="*" element={<Navigate to="/manuals" replace />} />
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
