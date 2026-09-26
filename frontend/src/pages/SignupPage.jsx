import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  confirmEmailVerification,
  fetchSignupMeta,
  registerEmployee,
  requestEmailVerification,
} from '../api'

const ID_RE = /^[A-Za-z0-9_]{3,50}$/
const EMP_NO_RE = /^\d{8}$/
const PASSWORD_RE = /^[A-Za-z0-9]{8,}$/
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const DOMESTIC_CODE_LABELS = { '1': '본국직원', '2': '현지직원' }

const FIELD_ERRORS = {
  id: 'ID should be 3-50 letters, digits, or underscores.',
  empNo: 'Employee number should be 8 digits.',
  password: 'Password should be 8 or more alphanumeric characters.',
  passwordConfirm: 'Passwords do not match.',
  email: 'Invalid email format.',
}

function validateField(name, value) {
  if (name === 'id') return ID_RE.test(value) ? '' : FIELD_ERRORS.id
  if (name === 'empNo') return EMP_NO_RE.test(value) ? '' : FIELD_ERRORS.empNo
  if (name === 'password') return PASSWORD_RE.test(value) ? '' : FIELD_ERRORS.password
  if (name === 'email') return EMAIL_RE.test(value) ? '' : FIELD_ERRORS.email
  return ''
}

function dedupeBy(rows, keyField, mapFn) {
  const seen = new Map()
  for (const row of rows) {
    if (!seen.has(row[keyField])) seen.set(row[keyField], mapFn(row))
  }
  return Array.from(seen.values())
}

function optionLabel(o) {
  return `${o.code}-${o.name_en}(${o.name_ko})`
}

function domesticLabel(code) {
  return DOMESTIC_CODE_LABELS[code] || code
}

function formatTimer(totalSeconds) {
  const m = String(Math.floor(totalSeconds / 60)).padStart(2, '0')
  const s = String(totalSeconds % 60).padStart(2, '0')
  return `${m}:${s}`
}

const EMPTY_VERIFY = { status: 'idle', remaining: 0, code: '', error: '', sentFor: '' }

export default function SignupPage() {
  const navigate = useNavigate()

  const [form, setForm] = useState({
    id: '',
    empNo: '',
    password: '',
    passwordConfirm: '',
    email: '',
    domesticCode: '',
    companyCode: '',
    teamCode: '',
    partCode: '',
    positionCode: '',
    permissionCode: '',
    langCode: '',
    countries: [],
  })
  const [fieldErrors, setFieldErrors] = useState({})

  const [meta, setMeta] = useState({ teams: [], positions: [], permissions: [], languages: [], countries: [] })
  const [metaError, setMetaError] = useState('')

  const [verify, setVerify] = useState(EMPTY_VERIFY)
  const [submitting, setSubmitting] = useState(false)
  const timerRef = useRef(null)

  useEffect(() => {
    fetchSignupMeta().then(setMeta).catch((err) => setMetaError(err.message))
    return () => clearTimer()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function clearTimer() {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }

  function startTimer() {
    clearTimer()
    timerRef.current = setInterval(() => {
      setVerify((prev) => {
        if (prev.remaining <= 1) {
          clearTimer()
          return { ...EMPTY_VERIFY }
        }
        return { ...prev, remaining: prev.remaining - 1 }
      })
    }, 1000)
  }

  const domesticCodes = useMemo(
    () => dedupeBy(meta.teams, 'domestic_code', (r) => ({ code: r.domestic_code })),
    [meta.teams],
  )
  const companies = useMemo(
    () => dedupeBy(
      meta.teams.filter((r) => r.domestic_code === form.domesticCode),
      'company_code',
      (r) => ({ code: r.company_code, name_ko: r.company_name_ko, name_en: r.company_name_en }),
    ),
    [meta.teams, form.domesticCode],
  )
  const teamsForCompany = useMemo(
    () => dedupeBy(
      meta.teams.filter((r) => r.domestic_code === form.domesticCode && r.company_code === form.companyCode),
      'team_code',
      (r) => ({ code: r.team_code, name_ko: r.team_name_ko, name_en: r.team_name_en }),
    ),
    [meta.teams, form.domesticCode, form.companyCode],
  )
  const partsForTeam = useMemo(
    () => meta.teams
      .filter((r) => r.domestic_code === form.domesticCode && r.company_code === form.companyCode && r.team_code === form.teamCode)
      .map((r) => ({ code: r.part_code, name_ko: r.part_name_ko, name_en: r.part_name_en })),
    [meta.teams, form.domesticCode, form.companyCode, form.teamCode],
  )

  const emailFormatValid = EMAIL_RE.test(form.email)

  function handleChange(e) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setFieldErrors((prev) => ({ ...prev, [name]: '' }))
  }

  function handleBlur(e) {
    const { name, value } = e.target
    if (name === 'passwordConfirm') {
      setFieldErrors((prev) => ({
        ...prev,
        passwordConfirm: value !== form.password ? FIELD_ERRORS.passwordConfirm : '',
      }))
      return
    }
    setFieldErrors((prev) => ({ ...prev, [name]: validateField(name, value) }))
  }

  function handleEmailChange(e) {
    const value = e.target.value
    setForm((prev) => ({ ...prev, email: value }))
    setFieldErrors((prev) => ({ ...prev, email: '' }))
    if (verify.status !== 'idle' && value !== verify.sentFor) {
      clearTimer()
      setVerify({ ...EMPTY_VERIFY })
    }
  }

  async function handleSendCode() {
    try {
      const data = await requestEmailVerification(form.email)
      clearTimer()
      setVerify({ status: 'sent', remaining: data.expires_in_seconds || 300, code: '', error: '', sentFor: form.email })
      startTimer()
    } catch (err) {
      setVerify((prev) => ({ ...prev, error: err.message }))
    }
  }

  function handleCodeChange(e) {
    const value = e.target.value
    setVerify((prev) => ({ ...prev, code: value, error: '' }))
  }

  async function handleVerifyClick() {
    try {
      await confirmEmailVerification(verify.sentFor, verify.code)
      clearTimer()
      setVerify((prev) => ({ ...prev, status: 'verified', remaining: 0, error: '' }))
    } catch (err) {
      setVerify((prev) => ({ ...prev, error: err.message }))
    }
  }

  function handleDomesticChange(e) {
    setForm((prev) => ({ ...prev, domesticCode: e.target.value, companyCode: '', teamCode: '', partCode: '' }))
  }

  function handleCompanyChange(e) {
    setForm((prev) => ({ ...prev, companyCode: e.target.value, teamCode: '', partCode: '' }))
  }

  function handleTeamChange(e) {
    setForm((prev) => ({ ...prev, teamCode: e.target.value, partCode: '' }))
  }

  function handlePartChange(e) {
    setForm((prev) => ({ ...prev, partCode: e.target.value }))
  }

  function handleCountryToggle(code) {
    setForm((prev) => ({
      ...prev,
      countries: prev.countries.includes(code)
        ? prev.countries.filter((c) => c !== code)
        : [...prev.countries, code],
    }))
  }

  async function handleSubmit(e) {
    e.preventDefault()

    const idError = validateField('id', form.id)
    const empNoError = validateField('empNo', form.empNo)
    const passwordError = validateField('password', form.password)
    const passwordConfirmError = form.passwordConfirm !== form.password ? FIELD_ERRORS.passwordConfirm : ''
    const emailError = validateField('email', form.email)
    setFieldErrors({
      id: idError, empNo: empNoError, password: passwordError,
      passwordConfirm: passwordConfirmError, email: emailError,
    })

    const allFilled = form.id && form.empNo && form.password && form.passwordConfirm && form.email
      && form.domesticCode && form.companyCode && form.teamCode && form.partCode
      && form.positionCode && form.permissionCode && form.langCode

    if (idError || empNoError || passwordError || passwordConfirmError || emailError || !allFilled) {
      window.alert('모든 정보를 올바르게 입력해 주세요.')
      return
    }
    if (verify.status !== 'verified' || verify.sentFor !== form.email) {
      window.alert('이메일 인증을 완료해 주세요.')
      return
    }

    const teamRow = meta.teams.find(
      (r) => r.domestic_code === form.domesticCode && r.company_code === form.companyCode
        && r.team_code === form.teamCode && r.part_code === form.partCode,
    )
    if (!teamRow) {
      window.alert('소속 팀 정보를 다시 선택해 주세요.')
      return
    }

    setSubmitting(true)
    try {
      await registerEmployee({
        id: form.id,
        emp_no: form.empNo,
        password: form.password,
        email: form.email,
        team_code: teamRow.org_code,
        position_code: form.positionCode,
        permission_code: form.permissionCode,
        lang_code: form.langCode,
        countries: form.countries,
      })
      window.alert('회원가입이 완료되었습니다. 로그인 후 이용해주세요.')
      navigate('/login')
    } catch (err) {
      window.alert(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="signup-page">
      <form className="signup-card" onSubmit={handleSubmit}>
        <h1 className="signup-title">회원가입</h1>

        {metaError && <p className="signup-meta-error">{metaError}</p>}

        <div className="field-row-4">
          <div className={`field${fieldErrors.empNo ? ' field--invalid' : ''}`}>
            <label htmlFor="su-emp-no">사번</label>
            <input
              id="su-emp-no"
              name="empNo"
              type="text"
              inputMode="numeric"
              maxLength={8}
              placeholder="8자리 숫자"
              value={form.empNo}
              onChange={handleChange}
              onBlur={handleBlur}
            />
            {fieldErrors.empNo && <p className="field-error">{fieldErrors.empNo}</p>}
          </div>

          <div className={`field${fieldErrors.id ? ' field--invalid' : ''}`}>
            <label htmlFor="su-id">ID</label>
            <input
              id="su-id"
              name="id"
              type="text"
              maxLength={50}
              placeholder="영문/숫자/_ 3~50자"
              value={form.id}
              onChange={handleChange}
              onBlur={handleBlur}
            />
            {fieldErrors.id && <p className="field-error">{fieldErrors.id}</p>}
          </div>

          <div className={`field${fieldErrors.password ? ' field--invalid' : ''}`}>
            <label htmlFor="su-password">PW</label>
            <input
              id="su-password"
              name="password"
              type="password"
              placeholder="8자 이상 영문/숫자"
              value={form.password}
              onChange={handleChange}
              onBlur={handleBlur}
            />
            {fieldErrors.password && <p className="field-error">{fieldErrors.password}</p>}
          </div>

          <div className={`field${fieldErrors.passwordConfirm ? ' field--invalid' : ''}`}>
            <label htmlFor="su-password-confirm">PW 확인</label>
            <input
              id="su-password-confirm"
              name="passwordConfirm"
              type="password"
              placeholder="비밀번호 재입력"
              value={form.passwordConfirm}
              onChange={handleChange}
              onBlur={handleBlur}
            />
            {fieldErrors.passwordConfirm && <p className="field-error">{fieldErrors.passwordConfirm}</p>}
          </div>
        </div>

        <div className={`field${fieldErrors.email ? ' field--invalid' : ''}`}>
          <label htmlFor="su-email">이메일주소</label>
          <div className="verify-row">
            <input
              id="su-email"
              name="email"
              type="email"
              placeholder="name@example.com"
              value={form.email}
              onChange={handleEmailChange}
              onBlur={handleBlur}
            />
            {verify.status !== 'verified' && (
              <button
                type="button"
                className="secondary"
                disabled={!(emailFormatValid && verify.status === 'idle')}
                onClick={handleSendCode}
              >
                인증번호발송
              </button>
            )}
          </div>
          {fieldErrors.email && <p className="field-error">{fieldErrors.email}</p>}

          {verify.status !== 'idle' && (
            <div className="verify-code-row">
              <input
                type="password"
                inputMode="numeric"
                maxLength={6}
                placeholder="인증번호 6자리"
                value={verify.code}
                onChange={handleCodeChange}
                disabled={verify.status === 'verified'}
              />
              {verify.status === 'sent' && (
                <span className="verify-timer">{formatTimer(verify.remaining)}</span>
              )}
              {verify.status === 'sent' && (
                <button type="button" className="secondary" onClick={handleVerifyClick}>인증하기</button>
              )}
              {verify.status === 'verified' && (
                <span className="verify-ok">인증 완료</span>
              )}
            </div>
          )}
          {verify.error && <p className="field-error">{verify.error}</p>}
        </div>

        <div className="field-row-4">
          <div className="field">
            <label htmlFor="su-domestic">본국행원여부</label>
            <select id="su-domestic" value={form.domesticCode} onChange={handleDomesticChange}>
              <option value="">선택</option>
              {domesticCodes.map((d) => (
                <option key={d.code} value={d.code}>{domesticLabel(d.code)}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="su-company">회사</label>
            <select id="su-company" value={form.companyCode} onChange={handleCompanyChange} disabled={!form.domesticCode}>
              <option value="">선택</option>
              {companies.map((c) => (
                <option key={c.code} value={c.code}>{optionLabel(c)}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="su-team">팀</label>
            <select id="su-team" value={form.teamCode} onChange={handleTeamChange} disabled={!form.companyCode}>
              <option value="">선택</option>
              {teamsForCompany.map((t) => (
                <option key={t.code} value={t.code}>{optionLabel(t)}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="su-part">파트</label>
            <select id="su-part" value={form.partCode} onChange={handlePartChange} disabled={!form.teamCode}>
              <option value="">선택</option>
              {partsForTeam.map((p) => (
                <option key={p.code} value={p.code}>{optionLabel(p)}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="field-row-3">
          <div className="field">
            <label htmlFor="su-position">직급</label>
            <select
              id="su-position"
              value={form.positionCode}
              onChange={(e) => setForm((prev) => ({ ...prev, positionCode: e.target.value }))}
            >
              <option value="">선택</option>
              {meta.positions.map((p) => (
                <option key={p.code} value={p.code}>{optionLabel(p)}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="su-permission">보유 권한</label>
            <select
              id="su-permission"
              value={form.permissionCode}
              onChange={(e) => setForm((prev) => ({ ...prev, permissionCode: e.target.value }))}
            >
              <option value="">선택</option>
              {meta.permissions.map((p) => (
                <option key={p.code} value={p.code}>{optionLabel(p)}</option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="su-lang">언어 코드</label>
            <select
              id="su-lang"
              value={form.langCode}
              onChange={(e) => setForm((prev) => ({ ...prev, langCode: e.target.value }))}
            >
              <option value="">선택</option>
              {meta.languages.map((l) => (
                <option key={l.code} value={l.code}>{l.code}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="field">
          <label>담당국가</label>
          <div className="checkbox-grid">
            {meta.countries.map((c) => (
              <label key={c.code} className="checkbox-item">
                <input
                  type="checkbox"
                  checked={form.countries.includes(c.code)}
                  onChange={() => handleCountryToggle(c.code)}
                />
                {form.langCode === 'EN' ? c.name_en : c.name_ko}
              </label>
            ))}
          </div>
        </div>

        <button type="submit" className="primary" disabled={submitting}>
          {submitting ? '가입 처리 중...' : '가입하기'}
        </button>

        <p className="foot">
          이미 계정이 있으신가요? <Link to="/login">로그인</Link>
        </p>
      </form>
    </div>
  )
}
