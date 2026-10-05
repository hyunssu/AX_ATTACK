import { useEffect, useState } from "react";
import TermManager from '../components/TermManager'

function TermListPage() {
  const [terms, setTerms] = useState([]);
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);

  // 페이징
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  useEffect(() => {
    const loadTerms = async () => {
      try {
        const response = await fetch("/api/terms");

        if (!response.ok) {
          throw new Error("용어 조회 실패");
        }

        const data = await response.json();
        setTerms(data.terms || []);
      } catch (error) {
        console.error(error);
        alert("용어 조회에 실패했습니다.");
      } finally {
        setLoading(false);
      }
    };

    loadTerms();
  }, []);

  // 검색
  const filteredTerms = terms.filter((term) => {
    const keyword = searchText.toLowerCase();

    return (
      term.term_name?.toLowerCase().includes(keyword) ||
      term.keyword?.toLowerCase().includes(keyword) ||
      term.definition?.toLowerCase().includes(keyword) ||
      term.category?.toLowerCase().includes(keyword)
    );
  });

  // 검색어가 변경되면 1페이지로 이동
  useEffect(() => {
    setCurrentPage(1);
  }, [searchText]);

  // 전체 페이지 수
  const totalPages = Math.ceil(filteredTerms.length / pageSize);

  // 현재 페이지에 표시할 데이터
  const startIndex = (currentPage - 1) * pageSize;
  const currentTerms = filteredTerms.slice(
    startIndex,
    startIndex + pageSize
  );

  if (loading) {
    return <div>조회 중...</div>;
  }

  return (
    <div
      style={{
        padding: "28px 30px",
        backgroundColor: "#fff",
        minHeight: "100%",
      }}
    >
      <h3>신규 단어 조회</h3>

      {/* 검색 영역 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          marginTop: "20px",
          marginBottom: "15px",
        }}
      >
        <input
          type="text"
          placeholder="용어명, Keyword, 정의, 분류 검색"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{
            width: "350px",
            height: "38px",
            padding: "0 12px",
            border: "1px solid #dfe3e8",
            borderRadius: "5px",
            fontSize: "13px",
            outline: "none",
            boxSizing: "border-box",
          }}
        />
        <div style={{ marginLeft: '8px' }}>
          <TermManager onRegistered={async () => {
            const response = await fetch('/api/terms')
            if (!response.ok) throw new Error('용어 목록을 새로고침하지 못했습니다.')
            const data = await response.json()
            setTerms(data.terms || [])
          }} />
        </div>

        <button
          onClick={() => setSearchText("")}
          style={{
            marginLeft: "8px",
            height: "38px",
            padding: "0 15px",
            border: "1px solid #dfe3e8",
            borderRadius: "5px",
            backgroundColor: "#fff",
            color: "#555",
            fontSize: "13px",
            cursor: "pointer",
          }}
        >
          초기화
        </button>
      </div>

      {/* 검색 결과 건수 */}
      <div style={{ marginBottom: "10px" }}>
        총 {filteredTerms.length}건
      </div>

      {/* 용어 목록 */}
      <table
        style={{
          width: "100%",
          borderCollapse: "separate",
          borderSpacing: 0,
          border: "1px solid #e1e5eb",
          borderRadius: "6px",
          overflow: "hidden",
          backgroundColor: "#fff",
        }}
      >
        <thead>
          <tr>
            <th style={thStyle}>번호</th>
            <th style={thStyle}>용어명</th>
            <th style={thStyle}>동의어 및 약어</th>
            <th style={thStyle}>정의</th>
            <th style={thStyle}>분류</th>
            <th style={thStyle}>등록일</th>
          </tr>
        </thead>

        <tbody>
          {currentTerms.length === 0 ? (
            <tr>
              <td colSpan="6" style={tdStyle}>
                검색 결과가 없습니다.
              </td>
            </tr>
          ) : (
            currentTerms.map((term) => (
              <tr key={term.term_id}>
                <td style={tdStyle}>{term.term_id}</td>
                <td style={tdStyle}>{term.term_name}</td>
                <td style={tdStyle}>{term.keyword}</td>
                <td style={tdStyle}>{term.definition}</td>
                <td style={tdStyle}>{term.category}</td>
                <td style={tdStyle}>
                  {term.created_at
                    ? new Date(term.created_at).toLocaleDateString()
                    : ""}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* 페이징 */}
      {totalPages > 0 && (
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: "4px",
            marginTop: "25px",
            marginBottom: "10px",
          }}
        >
          {/* 이전 */}
          <button
            onClick={() => setCurrentPage((prev) => prev - 1)}
            disabled={currentPage === 1}
            style={pageButtonStyle(currentPage === 1)}
          >
            이전
          </button>

          {/* 페이지 번호 */}
          {Array.from(
            { length: totalPages },
            (_, index) => index + 1
          ).map((page) => (
            <button
              key={page}
              onClick={() => setCurrentPage(page)}
              style={pageNumberStyle(currentPage === page)}
            >
              {page}
            </button>
          ))}

          {/* 다음 */}
          <button
            onClick={() => setCurrentPage((prev) => prev + 1)}
            disabled={currentPage === totalPages}
            style={pageButtonStyle(currentPage === totalPages)}
          >
            다음
          </button>
        </div>
      )}
    </div>
  );
}

const thStyle = {
  borderTop: "1px solid #e1e5eb",
  borderBottom: "1px solid #e1e5eb",
  padding: "12px 10px",
  backgroundColor: "#f7f8fa",
  color: "#1b2f50",
  fontSize: "13px",
  fontWeight: "600",
  textAlign: "center",
};

const tdStyle = {
  borderBottom: "1px solid #edf0f3",
  padding: "12px 10px",
  color: "#555",
  fontSize: "13px",
  textAlign: "center",
};

const pageButtonStyle = (disabled) => ({
  minWidth: "60px",
  height: "34px",
  padding: "0 10px",
  border: "1px solid #dfe3e8",
  borderRadius: "4px",
  backgroundColor: "#fff",
  color: disabled ? "#c5c9ce" : "#555",
  fontSize: "12px",
  cursor: disabled ? "default" : "pointer",
});

const pageNumberStyle = (active) => ({
  minWidth: "34px",
  height: "34px",
  padding: "0 8px",
  border: active ? "1px solid #1b2f50" : "1px solid #dfe3e8",
  borderRadius: "4px",
  backgroundColor: active ? "#1b2f50" : "#fff",
  color: active ? "#fff" : "#555",
  fontSize: "12px",
  fontWeight: active ? "600" : "400",
  cursor: "pointer",
});
export default TermListPage;
