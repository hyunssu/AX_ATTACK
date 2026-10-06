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

  // 승인 관련
  const [approvalModal, setApprovalModal] = useState({
  open: false,
  termId: null,
  approvalYn: null,
  });

  const handleApprovalChange = (termId, approvalYn) => {
  setApprovalModal({
    open: true,
    termId,
    approvalYn,
  });
  };

  const confirmApprovalChange = async () => {
    const { termId, approvalYn } = approvalModal;

    try {
      const response = await fetch(`/api/terms/${termId}/approval`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          approval_yn: approvalYn,
        }),
      });

      if (!response.ok) {
        throw new Error("승인여부 변경 실패");
      }

      setTerms((prevTerms) =>
        prevTerms.map((term) =>
          term.term_id === termId
            ? { ...term, approval_yn: approvalYn }
            : term
        )
      );

      setApprovalModal({
        open: false,
        termId: null,
        approvalYn: null,
      });
    } catch (error) {
      console.error(error);
      alert("승인여부 변경에 실패했습니다.");
    }
  };


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
            <th style={thStyle}>승인여부</th>
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
                  <select
                    value={term.approval_yn || "N"}
                    onChange={(e) =>
                      handleApprovalChange(term.term_id, e.target.value)
                    }
                    style={{
                      padding: "5px 8px",
                      border: "1px solid #dfe3e8",
                      borderRadius: "4px",
                      fontSize: "12px",
                    }}
                  >
                    <option value="N">미승인</option>
                    <option value="Y">승인</option>
                  </select>
                </td>
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

      {approvalModal.open && (
      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(0, 0, 0, 0.4)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          zIndex: 1000,
        }}
      >
        <div
          style={{
            width: "380px",
            backgroundColor: "#fff",
            borderRadius: "8px",
            padding: "25px",
            boxShadow: "0 4px 15px rgba(0, 0, 0, 0.2)",
          }}
        >
          <h3
            style={{
              margin: "0 0 15px",
              color: "#1b2f50",
              fontSize: "17px",
            }}
          >
            승인 상태 변경
          </h3>

          <p
            style={{
              margin: "0 0 25px",
              color: "#555",
              fontSize: "14px",
            }}
          >
            승인 상태를{" "}
            <strong>
              {approvalModal.approvalYn === "Y" ? "승인" : "미승인"}
            </strong>
            으로 변경하시겠습니까?
          </p>

          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: "8px",
            }}
          >
            <button
              onClick={() =>
                setApprovalModal({
                  open: false,
                  termId: null,
                  approvalYn: null,
                })
              }
              style={{
                padding: "9px 18px",
                border: "1px solid #dfe3e8",
                borderRadius: "4px",
                backgroundColor: "#fff",
                color: "#555",
                cursor: "pointer",
              }}
            >
              취소
            </button>

            <button
              onClick={confirmApprovalChange}
              style={{
                padding: "9px 18px",
                border: "1px solid #1b2f50",
                borderRadius: "4px",
                backgroundColor: "#1b2f50",
                color: "#fff",
                cursor: "pointer",
              }}
            >
              확인
            </button>
          </div>
        </div>
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
