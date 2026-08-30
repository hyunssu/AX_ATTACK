import { Link, useNavigate } from 'react-router-dom'
import ManualUploadForm from '../components/ManualUploadForm'

export default function ManualRegisterPage() {
  const navigate = useNavigate()

  return (
    <main className="page-layout page-layout--wide">
      <Link to="/manuals" className="back-link">← 매뉴얼 목록으로</Link>
      <div className="eyebrow">NEW MANUAL</div>
      <h1 className="hero__title hero__title--sm">새 매뉴얼 등록</h1>
      <p className="hero__subtitle">
        파일을 분석하면 여신/수신/외환/자금/카드/고객 등으로 자동 분류하고, 여러 매뉴얼로 나눠 등록할 내용을 확인할 수 있어요.
      </p>
      <section className="panel">
        <ManualUploadForm onCreated={() => navigate('/manuals')} />
      </section>
    </main>
  )
}
