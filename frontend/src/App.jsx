import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import Header from './components/Header'
import AboutPage from './pages/AboutPage'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import MyPage from './pages/MyPage'
import QAPage from './pages/QAPage'
import FAQReviewPage from './pages/FAQReviewPage'
import MindMapPage from './pages/MindMapPage'
import TermTestPage from './pages/TermsTestPage'
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

function FAQRoleGate({ children }) {
  const { role } = useAuth()
  if (role !== 'ADMIN') return <Navigate to="/qa" replace />
  return children
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        path="/about"
        element={(
          <ProtectedLayout>
            <AboutPage />
          </ProtectedLayout>
        )}
      />
      <Route
        path="/faqs"
        element={(
          <ProtectedLayout>
            <FAQRoleGate>
              <FAQReviewPage />
            </FAQRoleGate>
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
      <Route
        path="/mindmap"
        element={(
          <ProtectedLayout>
            <MindMapPage />
          </ProtectedLayout>
        )}
      />
      <Route
        path="/mypage"
        element={(
          <ProtectedLayout>
            <MyPage />
          </ProtectedLayout>
        )}
      />
      <Route
        path="/term-test"
        element={<TermTestPage />}
      />
      <Route path="*" element={<Navigate to="/mindmap" replace />} />
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
