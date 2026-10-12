import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { confirmPasswordReset, requestPasswordReset } from '../api'

const PASSWORD_RE = /^[A-Za-z0-9]{8,}$/
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function formatTimer(totalSeconds) {
  const m = String(Math.floor(totalSeconds / 60)).padStart(2, '0')
  const s = String(totalSeconds % 60).padStart(2, '0')
  return `${m}:${s}`
}

// 회원가입 화면의 이메일 인증 UI/스타일(.signup-page)을 그대로 재사용한다.
export default function ResetPasswordPage() {
  const navigate = useNavigate()

  const [id, setId] = useState('')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [sent, setSent] = useState(false)
  const [remaining, setRemaining] = useState(0)
  const [sending, setSending] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const timerRef = useRef(null)

  useEffect(() => () => clearTimer(), [])

  function clearTimer() {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  function startTimer(seconds) {
    clearTimer()
    setRemaining(seconds)
    timerRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearTimer()
          setSent(false)
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  function resetVerification() {
    clearTimer()
    setSent(false)
    setRemaining(0)
    setCode('')
  }

  async function handleSendCode() {
    if (!id.trim()) {
      setError('아이디를 입력하세요')
      return
    }
    if (!EMAIL_RE.test(email)) {
      setError('Invalid email format.')
      return
    }
    setError('')
    setSending(true)
    try {
      const data = await requestPasswordReset(id.trim(), email)
      setSent(true)
      setCode('')
      startTimer(data.expires_in_seconds || 300)
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!sent) {
      setError('먼저 인증번호를 발송해 주세요.')
      return
    }
    if (!code) {
      setError('인증번호를 입력하세요')
      return
    }
    if (!PASSWORD_RE.test(password)) {
      setError('Password should be 8 or more alphanumeric characters.')
      return
    }
    if (password !== passwordConfirm) {
      setError('Passwords do not match.')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      await confirmPasswordReset(id.trim(), email, code, password)
      clearTimer()
      window.alert('비밀번호가 재설정되었습니다. 새 비밀번호로 로그인해 주세요.')
      navigate('/login')
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="signup-page">
      <form className="signup-card reset-card" onSubmit={handleSubmit}>
        <h1 className="signup-title">비밀번호 찾기</h1>

        <div className="field">
          <label htmlFor="rp-id">ID</label>
          <input
            id="rp-id"
            type="text"
            autoComplete="username"
            value={id}
            onChange={(e) => { setId(e.target.value); setError(''); resetVerification() }}
          />
        </div>

        <div className="field">
          <label htmlFor="rp-email">가입 시 등록한 이메일</label>
          <div className="verify-row">
            <input
              id="rp-email"
              type="email"
              placeholder="name@example.com"
              value={email}
              onChange={(e) => { setEmail(e.target.value); setError(''); resetVerification() }}
            />
            <button
              type="button"
              className="secondary"
              disabled={sending || !id.trim() || !EMAIL_RE.test(email)}
              onClick={handleSendCode}
            >
              {sent ? '재발송' : '인증번호발송'}
            </button>
          </div>
          {sent && (
            <div className="verify-code-row">
              <input
                type="password"
                inputMode="numeric"
                maxLength={6}
                placeholder="인증번호 6자리"
                value={code}
                onChange={(e) => { setCode(e.target.value); setError('') }}
              />
              <span className="verify-timer">{formatTimer(remaining)}</span>
            </div>
          )}
        </div>

        <div className="field">
          <label htmlFor="rp-password">새 비밀번호</label>
          <input
            id="rp-password"
            type="password"
            autoComplete="new-password"
            placeholder="8자 이상 영문/숫자"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setError('') }}
          />
        </div>

        <div className="field">
          <label htmlFor="rp-password-confirm">새 비밀번호 확인</label>
          <input
            id="rp-password-confirm"
            type="password"
            autoComplete="new-password"
            placeholder="비밀번호 재입력"
            value={passwordConfirm}
            onChange={(e) => { setPasswordConfirm(e.target.value); setError('') }}
          />
        </div>

        {error && <p className="field-error" role="status">{error}</p>}

        <button type="submit" className="primary" disabled={submitting}>
          {submitting ? '처리 중...' : '비밀번호 재설정'}
        </button>

        <p className="foot">
          <Link to="/login">로그인으로 돌아가기</Link>
        </p>
      </form>
    </div>
  )
}
