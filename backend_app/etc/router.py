from fastapi import APIRouter, HTTPException
from .schemas import TermCreateRequest
from terms import ./terms 

router = APIRouter(prefix="/terms", tags=["terms"])

@router.post("/register")
def register_new_term(data: TermCreateRequest):
    try:
        # terms.py의 create_term 함수 호출
        new_term_id = create_term(
            term_name=data.term_name,
            definition=data.definition,
            keyword=data.keyword,    # 동의어/약어는 keyword 컬럼으로 저장
            category=data.category
        )
        
        return {
            "success": True, 
            "message": "신규 단어가 성공적으로 등록되었습니다.", 
            "term_id": new_term_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"단어 등록 실패: {str(e)}")