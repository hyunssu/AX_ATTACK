export default function AboutPage() {
  return (
    <main className="page-layout page-layout--wide">
      <section className="hero">
        <div className="eyebrow">ABOUT US</div>
        <h1 className="hero__title">일하는 방식을 더 정확하게</h1>
        <p className="hero__subtitle">업무 매뉴얼을 한곳에 모으고, AI가 그 안에서 답을 찾아드립니다</p>
      </section>
      <section className="about-grid">
        <div className="about-block">
          <div className="eyebrow">WHY</div>
          <p className="about-block__text">
            흩어진 매뉴얼과 공지를 매번 찾아 헤매는 대신, 등록된 문서 안에서 바로 답을 얻을 수 있도록 만들었습니다.
          </p>
        </div>
        <div className="about-block">
          <div className="eyebrow">HOW</div>
          <p className="about-block__text">
            업로드된 매뉴얼은 자동으로 섹션 단위로 나뉘어 저장되고, 질문을 하면 관련된 부분을 찾아 근거와 함께 답변합니다.
          </p>
        </div>
        <div className="about-block">
          <div className="eyebrow">WHAT'S NEXT</div>
          <p className="about-block__text">
            더 많은 매뉴얼과 더 정확한 답변을 목표로 계속 개선하고 있습니다.
          </p>
        </div>
      </section>
    </main>
  )
}
