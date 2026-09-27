import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { checkpointStaleRooms, loginEmployee } from '../api'
import { useAuth } from '../auth'

const REMEMBER_ID_KEY = 'manual_system_remembered_id'

function BrandMark() {
  return (
    <svg width="56" height="62" viewBox="0 0 106 118" aria-hidden="true">
      <path className="sd" d="M53 3 L103 115 L86 115 L73 86 L33 86 L20 115 L3 115 Z M53 41 L67 72 L39 72 Z" />
      <path className="st" d="M53 3 L103 115 L86 115 L73 86 L33 86 L20 115 L3 115 Z M53 41 L67 72 L39 72 Z" />
    </svg>
  )
}

export default function LoginPage() {
  const [username, setUsername] = useState(() => localStorage.getItem(REMEMBER_ID_KEY) || '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [rememberId, setRememberId] = useState(() => Boolean(localStorage.getItem(REMEMBER_ID_KEY)))

  const { login } = useAuth()
  const navigate = useNavigate()

  const frameRef = useRef(null)
  const stageRef = useRef(null)
  const stackRef = useRef(null)
  const linesRef = useRef(null)
  const cardRef = useRef(null)
  const anchorRef = useRef(null)
  const usernameInputRef = useRef(null)
  const passwordInputRef = useRef(null)
  const scaleRef = useRef(1)

  const fit = useCallback(() => {
    const frame = frameRef.current
    if (!frame) return
    let scale = Math.min(1, (window.innerWidth - 48) / 620, (window.innerHeight - 120) / 380)
    if (scale < 0.34) scale = 0.34
    scaleRef.current = scale
    frame.style.transform = `scale(${scale})`
  }, [])

  const layout = useCallback(() => {
    const stage = stageRef.current
    const lines = linesRef.current
    const card = cardRef.current
    const anchorEl = anchorRef.current
    if (!stage || !lines || !card || !anchorEl) return
    const scale = scaleRef.current
    const s = stage.getBoundingClientRect()
    const lb = lines.getBoundingClientRect()
    const ab = anchorEl.getBoundingClientRect()
    const ox = (ab.left + ab.width / 2 - lb.left) / scale
    const oy = (ab.top + ab.height / 2 - lb.top) / scale
    lines.style.transformOrigin = `${ox}px ${oy}px`
    const cx = (lb.left - s.left) / scale + ox
    const cy = (lb.top - s.top) / scale + oy
    stackRef.current.style.setProperty('--shift', `${Math.round(90 - cx)}px`)
    card.style.top = `${Math.round(cy - card.offsetHeight / 2)}px`
  }, [])

  const play = useCallback(() => {
    const stage = stageRef.current
    if (!stage) return
    stage.classList.remove('go', 'end')
    // force reflow so the removed animation classes actually restart
    void stage.offsetWidth
    fit()
    layout()
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    stage.classList.add(reduceMotion ? 'end' : 'go')
    setError('')
  }, [fit, layout])

  useEffect(() => {
    const onResize = () => { fit(); layout() }
    window.addEventListener('resize', onResize)
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(play)
    } else {
      play()
    }
    return () => window.removeEventListener('resize', onResize)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!username.trim()) {
      setError('아이디를 입력하세요')
      usernameInputRef.current?.focus()
      return
    }
    if (!password) {
      setError('비밀번호를 입력하세요')
      passwordInputRef.current?.focus()
      return
    }
    setError('')
    setLoading(true)
    try {
      const data = await loginEmployee(username, password)
      login(data.access_token, username, data.permission_code)
      if (rememberId) {
        localStorage.setItem(REMEMBER_ID_KEY, username)
      } else {
        localStorage.removeItem(REMEMBER_ID_KEY)
      }
      checkpointStaleRooms().catch(() => {})
      navigate('/mindmap')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function handleUsernameKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault()
      passwordInputRef.current?.focus()
    }
  }

  return (
    <div className="login-page">
      <div className="frame" ref={frameRef}>
        <div className="stage" ref={stageRef}>
          <div className="stack" ref={stackRef}>
            <div className="lines" ref={linesRef}>
              <div className="ln r1">
                <span className="ch mark" style={{ '--d': '0s' }}><BrandMark /></span>
                <span className="ch x" style={{ '--d': '.09s', '--o': '2.42s' }}>I</span>
                <span className="ch x" style={{ '--d': '.18s', '--o': '2.34s' }}>T</span>
                <span className="ch x" style={{ '--d': '.27s', '--o': '2.26s' }}>H</span>
                <span className="ch x" style={{ '--d': '.36s', '--o': '2.18s' }}>E</span>
                <span className="ch x" style={{ '--d': '.45s', '--o': '2.1s' }}>R</span>
              </div>

              <div className="ln r2">
                <span className="ch mark" ref={anchorRef} style={{ '--d': '.54s' }}><BrandMark /></span>
                <span className="ch x" style={{ '--d': '.63s', '--o': '2.1s' }}>I</span>
              </div>

              <div className="ln r3">
                <span className="ch mark" style={{ '--d': '.72s' }}><BrandMark /></span>
                <span className="ch x" style={{ '--d': '.81s', '--o': '2.34s' }}>G</span>
                <span className="ch x" style={{ '--d': '.9s', '--o': '2.26s' }}>E</span>
                <span className="ch x" style={{ '--d': '.99s', '--o': '2.18s' }}>N</span>
                <span className="ch x" style={{ '--d': '1.08s', '--o': '2.1s' }}>T</span>
              </div>
            </div>
          </div>

          <form className="card" ref={cardRef} onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="lp-username">아이디</label>
              <input
                id="lp-username"
                ref={usernameInputRef}
                type="text"
                autoComplete="username"
                placeholder="aither"
                value={username}
                onChange={(e) => { setUsername(e.target.value); setError('') }}
                onKeyDown={handleUsernameKeyDown}
              />
            </div>
            <div className="field" style={{ marginBottom: 8 }}>
              <label htmlFor="lp-password">비밀번호</label>
              <input
                id="lp-password"
                ref={passwordInputRef}
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError('') }}
              />
            </div>
            <label className="remember-id">
              <input
                type="checkbox"
                checked={rememberId}
                onChange={(e) => setRememberId(e.target.checked)}
              />
              ID 기억하기
            </label>
            <p className="msg" role="status" aria-live="polite">{error}</p>
            <button type="submit" className="primary" disabled={loading}>
              {loading ? '로그인 중...' : '로그인'}
            </button>
            <p className="foot">
              <a href="#" onClick={(e) => e.preventDefault()}>비밀번호 찾기</a>
              {' · '}
              <Link to="/signup">계정 만들기</Link>
            </p>
          </form>
        </div>
      </div>

      <button type="button" className="replay" onClick={play}>화면 초기화</button>
    </div>
  )
}
