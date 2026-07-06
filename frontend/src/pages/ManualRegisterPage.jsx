import { Link, useNavigate } from 'react-router-dom'
import ManualUploadForm from '../components/ManualUploadForm'

export default function ManualRegisterPage() {
  const navigate = useNavigate()

  return (
    <main className="manual-register-layout">
      <div className="manual-register-header">
        <Link to="/manuals" className="manual-register-back">← 매뉴얼 목록으로</Link>
        <h2 className="manual-register-title">새 매뉴얼 등록</h2>
      </div>
      <div className="manual-register-body">
        <section className="panel manual-register-form-panel">
          <ManualUploadForm onCreated={() => navigate('/manuals')} />
        </section>
        <aside className="panel manual-register-help">
          <h3 className="panel__title">등록 절차</h3>
          <ol className="manual-register-steps">
            <li>제목을 입력하고 PDF 또는 Markdown 파일을 선택하세요.</li>
            <li>"미리보기"를 누르면 문서가 어떤 단위(장/섹션)로 나뉘는지 미리 확인할 수 있어요.</li>
            <li>"등록"을 누르면 파일 변환 → 청킹 → 임베딩 순으로 자동 처리되고, 진행 상황이 표시돼요.</li>
          </ol>
        </aside>
      </div>
    </main>
  )
}
