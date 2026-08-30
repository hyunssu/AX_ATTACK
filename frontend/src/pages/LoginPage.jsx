import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { checkpointStaleRooms, login as loginApi, register as registerApi } from '../api'
import { useAuth } from '../auth'

function mkSeries(v, vol, n = 60) {
  const s = []
  let c = v * (1 - vol * 8)
  for (let i = 0; i < n; i++) { c += (Math.random() - 0.485) * vol * v; s.push(c) }
  s[s.length - 1] = v
  return s
}

const MKT_INIT = {
  kospi:  { val: 2748.31, open: 2714.19 },
  kosdaq: { val: 876.44,  open: 879.25  },
  usd:    { val: 1384.50, open: 1381.30 },
  eur:    { val: 1512.30, open: 1517.40 },
  jpy:    { val: 9.18,    open: 9.14    },
  cny:    { val: 191.30,  open: 191.70  },
}

function MarketPanel() {
  const [data, setData] = useState(() => {
    const d = {}
    for (const [k, v] of Object.entries(MKT_INIT)) {
      d[k] = { ...v, series: mkSeries(v.val, k === 'kospi' ? 0.0035 : k === 'kosdaq' ? 0.004 : 0.0007) }
    }
    return d
  })

  const cvKospi  = useRef(null)
  const cvKosdaq = useRef(null)
  const cvUsd = useRef(null)
  const cvEur = useRef(null)
  const cvJpy = useRef(null)
  const cvCny = useRef(null)
  const fxRefs = { usd: cvUsd, eur: cvEur, jpy: cvJpy, cny: cvCny }

  const drawSpark = useCallback((canvas, series, up) => {
    if (!canvas) return
    const pr = devicePixelRatio || 1
    const w = canvas.offsetWidth, h = canvas.offsetHeight
    canvas.width = w * pr; canvas.height = h * pr
    const ctx = canvas.getContext('2d')
    ctx.scale(pr, pr); ctx.clearRect(0, 0, w, h)
    const mn = Math.min(...series), mx = Math.max(...series), rng = mx - mn || 1
    const pad = h * 0.08
    const pts = series.map((v, i) => ({
      x: (i / (series.length - 1)) * w,
      y: h - pad - ((v - mn) / rng) * (h - pad * 2),
    }))
    const lc = up ? 'rgba(29,214,126,.85)' : 'rgba(255,100,100,.85)'
    const fa = up ? 'rgba(29,214,126,.20)' : 'rgba(255,100,100,.20)'
    const grd = ctx.createLinearGradient(0, 0, 0, h)
    grd.addColorStop(0, fa); grd.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y)
    for (let i = 1; i < pts.length; i++) {
      const cx = (pts[i-1].x + pts[i].x) / 2
      ctx.bezierCurveTo(cx, pts[i-1].y, cx, pts[i].y, pts[i].x, pts[i].y)
    }
    ctx.lineTo(pts[pts.length-1].x, h); ctx.lineTo(pts[0].x, h); ctx.closePath()
    ctx.fillStyle = grd; ctx.fill()
    ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y)
    for (let i = 1; i < pts.length; i++) {
      const cx = (pts[i-1].x + pts[i].x) / 2
      ctx.bezierCurveTo(cx, pts[i-1].y, cx, pts[i].y, pts[i].x, pts[i].y)
    }
    ctx.strokeStyle = lc; ctx.lineWidth = 1.5; ctx.stroke()
    const lp = pts[pts.length - 1]
    ctx.beginPath(); ctx.arc(lp.x, lp.y, 3, 0, Math.PI * 2)
    ctx.fillStyle = lc; ctx.fill()
  }, [])

  useEffect(() => {
    const tick = () => setData(prev => {
      const next = {}
      for (const [k, v] of Object.entries(prev)) {
        const vol = k === 'kospi' ? 0.0035 : k === 'kosdaq' ? 0.004 : 0.0007
        const val = v.val + (Math.random() - 0.49) * vol * v.val
        next[k] = { ...v, val, series: [...v.series.slice(-89), val] }
      }
      return next
    })
    const id = setInterval(tick, 2600)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    drawSpark(cvKospi.current,  data.kospi.series,  data.kospi.val  >= data.kospi.open)
    drawSpark(cvKosdaq.current, data.kosdaq.series, data.kosdaq.val >= data.kosdaq.open)
    for (const key of ['usd', 'eur', 'jpy', 'cny']) {
      drawSpark(fxRefs[key].current, data[key].series, data[key].val >= data[key].open)
    }
  }, [data, drawSpark]) // eslint-disable-line react-hooks/exhaustive-deps

  function fmt(v, d) { return v.toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d }) }
  function chgInfo(v, o) {
    const diff = v - o, up = diff >= 0
    return { txt: `${up ? '▲' : '▼'} ${Math.abs(diff / o * 100).toFixed(2)}%`, up }
  }

  const kc = chgInfo(data.kospi.val,  data.kospi.open)
  const dc = chgInfo(data.kosdaq.val, data.kosdaq.open)
  const FX = [
    { key: 'usd', flag: '🇺🇸', label: 'USD', unit: '달러', dec: 2 },
    { key: 'eur', flag: '🇪🇺', label: 'EUR', unit: '유로', dec: 2 },
    { key: 'jpy', flag: '🇯🇵', label: 'JPY', unit: '엔',   dec: 2 },
    { key: 'cny', flag: '🇨🇳', label: 'CNY', unit: '위안', dec: 2 },
  ]

  return (
    <div className="mp">
      <div className="mp__hd">한국 시장 현황</div>

      <div className="mp__indices">
        <div className={`mp__idx ${kc.up ? 'up' : 'dn'}`}>
          <div className="mp__idx-lbl">KOSPI · 코스피</div>
          <div className={`mp__idx-val ${kc.up ? 'up' : 'dn'}`}>{fmt(data.kospi.val, 2)}</div>
          <div className={`mp__idx-chg ${kc.up ? 'up' : 'dn'}`}>{kc.txt}</div>
          <canvas ref={cvKospi} className="mp__cv" />
        </div>
        <div className={`mp__idx ${dc.up ? 'up' : 'dn'}`}>
          <div className="mp__idx-lbl">KOSDAQ · 코스닥</div>
          <div className={`mp__idx-val ${dc.up ? 'up' : 'dn'}`}>{fmt(data.kosdaq.val, 2)}</div>
          <div className={`mp__idx-chg ${dc.up ? 'up' : 'dn'}`}>{dc.txt}</div>
          <canvas ref={cvKosdaq} className="mp__cv" />
        </div>
      </div>

      <div className="mp__fx-hd">환율 · Exchange Rates</div>
      <div className="mp__fx">
        {FX.map(({ key, flag, label, unit, dec }) => {
          const c = chgInfo(data[key].val, data[key].open)
          return (
            <div key={key} className="mp__fx-card">
              <div className="mp__fx-top">
                <span className="mp__fx-pair">{flag} {label}/KRW</span>
                <span className={`mp__fx-chg ${c.up ? 'up' : 'dn'}`}>{c.txt}</span>
              </div>
              <canvas ref={fxRefs[key]} className="mp__cv-sm" />
              <div className={`mp__fx-rate ${c.up ? 'up' : 'dn'}`}>{fmt(data[key].val, dec)}</div>
              <div className="mp__fx-unit">원 / 1 {unit}</div>
            </div>
          )
        })}
      </div>

      <div className="mp__demo">DEMO · 시뮬레이션 데이터 · 투자 참고용 아님</div>
    </div>
  )
}

export default function LoginPage() {
  const [tab, setTab] = useState('login')

  const [loginUsername, setLoginUsername] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)

  const [regUsername, setRegUsername] = useState('')
  const [regEmail, setRegEmail] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regConfirm, setRegConfirm] = useState('')
  const [regError, setRegError] = useState('')
  const [regLoading, setRegLoading] = useState(false)

  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleLogin(e) {
    e.preventDefault()
    setLoginError('')
    setLoginLoading(true)
    try {
      const data = await loginApi(loginUsername, loginPassword)
      login(data.access_token, data.username, data.role)
      checkpointStaleRooms().catch(() => {})
      navigate('/mindmap')
    } catch (err) {
      setLoginError(err.message)
    } finally {
      setLoginLoading(false)
    }
  }

  async function handleRegister(e) {
    e.preventDefault()
    setRegError('')
    if (regPassword !== regConfirm) { setRegError('비밀번호가 일치하지 않습니다.'); return }
    if (regPassword.length < 4) { setRegError('비밀번호는 4자 이상이어야 합니다.'); return }
    setRegLoading(true)
    try {
      const data = await registerApi(regUsername, regEmail, regPassword)
      login(data.access_token, data.username, data.role)
      navigate('/mindmap')
    } catch (err) {
      setRegError(err.message)
    } finally {
      setRegLoading(false)
    }
  }

  function switchTab(t) { setTab(t); setLoginError(''); setRegError('') }

  return (
    <div className="lp">
      <div className="lp__brand">
        <div className="lp__brand-wordmark">매뉴얼 관리 시스템</div>
        <MarketPanel />
      </div>

      <div className="lp__panel">
        <div className="lp__card">
          <div className="lp__tabs">
            <button type="button" className={`lp__tab${tab === 'login' ? ' lp__tab--active' : ''}`} onClick={() => switchTab('login')}>로그인</button>
            <button type="button" className={`lp__tab${tab === 'register' ? ' lp__tab--active' : ''}`} onClick={() => switchTab('register')}>회원가입</button>
          </div>

          {tab === 'login' ? (
            <form className="lp__form" onSubmit={handleLogin}>
              <div className="lp__field">
                <label className="lp__label">아이디</label>
                <input className="lp__input" type="text" placeholder="아이디를 입력하세요" value={loginUsername} onChange={e => setLoginUsername(e.target.value)} autoComplete="username" required />
              </div>
              <div className="lp__field">
                <label className="lp__label">비밀번호</label>
                <input className="lp__input" type="password" placeholder="비밀번호를 입력하세요" value={loginPassword} onChange={e => setLoginPassword(e.target.value)} autoComplete="current-password" required />
              </div>
              {loginError && <div className="lp__error">{loginError}</div>}
              <button type="submit" className="lp__submit" disabled={loginLoading}>{loginLoading ? '로그인 중...' : '로그인'}</button>
              <p className="lp__switch">계정이 없으신가요? <button type="button" className="lp__switch-btn" onClick={() => switchTab('register')}>회원가입</button></p>
            </form>
          ) : (
            <form className="lp__form" onSubmit={handleRegister}>
              <div className="lp__field">
                <label className="lp__label">아이디</label>
                <input className="lp__input" type="text" placeholder="사용할 아이디를 입력하세요" value={regUsername} onChange={e => setRegUsername(e.target.value)} autoComplete="username" required />
              </div>
              <div className="lp__field">
                <label className="lp__label">이메일</label>
                <input className="lp__input" type="email" placeholder="이메일 주소를 입력하세요" value={regEmail} onChange={e => setRegEmail(e.target.value)} autoComplete="email" required />
              </div>
              <div className="lp__field">
                <label className="lp__label">비밀번호</label>
                <input className="lp__input" type="password" placeholder="비밀번호 (4자 이상)" value={regPassword} onChange={e => setRegPassword(e.target.value)} autoComplete="new-password" required />
              </div>
              <div className="lp__field">
                <label className="lp__label">비밀번호 확인</label>
                <input className="lp__input" type="password" placeholder="비밀번호를 다시 입력하세요" value={regConfirm} onChange={e => setRegConfirm(e.target.value)} autoComplete="new-password" required />
              </div>
              {regError && <div className="lp__error">{regError}</div>}
              <button type="submit" className="lp__submit" disabled={regLoading}>{regLoading ? '처리 중...' : '회원가입'}</button>
              <p className="lp__switch">이미 계정이 있으신가요? <button type="button" className="lp__switch-btn" onClick={() => switchTab('login')}>로그인</button></p>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
