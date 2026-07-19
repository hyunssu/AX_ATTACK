import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { checkpointStaleRooms, login as loginApi } from '../api'
import { useAuth } from '../auth'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      const data = await loginApi(username, password)
      login(data.access_token, data.username)
      checkpointStaleRooms().catch(() => {})
      navigate('/manuals')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1 className="login-card__title">매뉴얼 관리 시스템</h1>
        <p className="login-card__subtitle">로그인 후 이용해 주세요</p>

        <input
          type="text"
          placeholder="아이디"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          type="password"
          placeholder="비밀번호"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && <div className="login-card__error">{error}</div>}

        <button type="submit" className="btn btn--primary login-card__submit">로그인</button>
      </form>
    </div>
  )
}
